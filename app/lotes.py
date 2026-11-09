"""Venta conjunta («lote de la caleta»).

Un bote solo, con 50 kg, no tiene poder para negociar: vende al precio que le pongan.
Si varios botes juntan su captura de una misma especie, la caleta puede ofrecer volumen a
una pescadería o restaurante y fijar un precio mínimo. Al cerrar la venta, el pago se
reparte en proporción a los kilos que aportó cada bote, y el precio queda registrado en
el desembarque de cada uno (sin tener que anotarlo dos veces).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app import analytics
from app.models import (Calidad, Comprador, Desembarque, Embarcacion, Especie, EstadoLote, Lote, LoteAporte,
                        Origen)


@dataclass
class Reparto:
    embarcacion_id: int
    bote: str
    kg: float
    porcentaje: float
    monto: int


@dataclass
class ResumenLote:
    lote: Lote
    especie: str
    kg_total: float
    botes: int
    aportes: list[Reparto] = field(default_factory=list)
    comprador: str = ""
    precio_intermediario: Optional[float] = None   # mediana pagada por intermediarios (30 días)

    @property
    def total_venta(self) -> Optional[int]:
        return sum(a.monto for a in self.aportes) if self.lote.precio_venta else None

    @property
    def ganancia_vs_intermediario(self) -> Optional[int]:
        """Cuánto más se gana (o se pierde) frente a vender cada uno por separado al intermediario."""
        precio = self.lote.precio_venta or self.lote.precio_minimo
        if self.precio_intermediario is None:
            return None
        return round((precio - self.precio_intermediario) * self.kg_total)


def repartir(aportes: list[tuple[int, str, float]], precio: int) -> list[Reparto]:
    """Reparte la venta en proporción a los kilos. aportes = [(embarcacion_id, nombre, kg)]."""
    total = sum(kg for *_, kg in aportes)
    if total <= 0:
        return []
    return [Reparto(eid, nombre, kg, kg / total * 100, round(kg * precio)) for eid, nombre, kg in aportes]


def crear_lote(s: Session, especie_id: int, precio_minimo: int, fecha: Optional[date] = None,
               quien: str = "", nota: str = "") -> Lote:
    esp = s.get(Especie, especie_id)
    if esp is None:
        raise ValueError("Elige una especie.")
    if not precio_minimo or precio_minimo < esp.precio_min or precio_minimo > esp.precio_max:
        raise ValueError(f"El precio mínimo de {esp.nombre} debe estar entre "
                         f"{analytics.clp(esp.precio_min)} y {analytics.clp(esp.precio_max)} por kilo.")
    lote = Lote(fecha=fecha or date.today(), especie_id=especie_id, precio_minimo=int(precio_minimo),
                creado_por=quien, nota=nota.strip())
    s.add(lote)
    s.commit()
    s.refresh(lote)
    return lote


def sumarse(s: Session, lote_id: int, embarcacion_id: int, kg: float) -> LoteAporte:
    lote = s.get(Lote, lote_id)
    if lote is None or lote.estado != EstadoLote.ABIERTO:
        raise ValueError("Esta venta conjunta ya no está abierta.")
    esp = s.get(Especie, lote.especie_id)
    if not kg or kg <= 0 or kg > esp.kg_max_salida:
        raise ValueError(f"Los kilos deben estar entre 1 y {esp.kg_max_salida:.0f}.")
    ya = s.exec(select(LoteAporte).where(LoteAporte.lote_id == lote_id,
                                         LoteAporte.embarcacion_id == embarcacion_id)).first()
    if ya:                      # si ya estaba, se actualizan sus kilos
        ya.kg = float(kg)
        aporte = ya
    else:
        aporte = LoteAporte(lote_id=lote_id, embarcacion_id=embarcacion_id, kg=float(kg))
    s.add(aporte)
    s.commit()
    s.refresh(aporte)
    return aporte


def retirarse(s: Session, lote_id: int, embarcacion_id: int) -> None:
    lote = s.get(Lote, lote_id)
    if lote is None or lote.estado != EstadoLote.ABIERTO:
        raise ValueError("Esta venta conjunta ya no está abierta.")
    for a in s.exec(select(LoteAporte).where(LoteAporte.lote_id == lote_id,
                                             LoteAporte.embarcacion_id == embarcacion_id)).all():
        s.delete(a)
    s.commit()


def resumen(s: Session, lote: Lote) -> ResumenLote:
    botes = {b.id: b.nombre for b in s.exec(select(Embarcacion)).all()}
    esp = s.get(Especie, lote.especie_id)
    filas = s.exec(select(LoteAporte).where(LoteAporte.lote_id == lote.id)).all()
    datos = [(a.embarcacion_id, botes.get(a.embarcacion_id, "?"), a.kg) for a in filas]
    precio = lote.precio_venta or lote.precio_minimo
    reparto = repartir(datos, precio)
    comp = s.get(Comprador, lote.comprador_id) if lote.comprador_id else None
    ref = analytics.precio_referencia(s, lote.especie_id, lote.fecha)
    p_int = None
    if not ref.por_comprador.empty:
        fila = ref.por_comprador[ref.por_comprador["comprador_tipo"] == "intermediario"]
        if not fila.empty and int(fila["count"].iloc[0]) >= 3:
            p_int = float(fila["median"].iloc[0])
    return ResumenLote(lote, esp.nombre, sum(kg for *_, kg in datos), len(datos), reparto,
                       f"{comp.nombre} ({comp.tipo.value})" if comp else "", p_int)


def lotes(s: Session, estado: Optional[EstadoLote] = None, limite: int = 20) -> list[ResumenLote]:
    q = select(Lote).order_by(Lote.fecha.desc(), Lote.id.desc())
    if estado:
        q = q.where(Lote.estado == estado)
    return [resumen(s, lt) for lt in s.exec(q.limit(limite)).all()]


def cerrar_venta(s: Session, lote_id: int, comprador_id: int, precio_venta: int, quien: str = "") -> ResumenLote:
    """Cierra la venta: guarda comprador y precio, y completa el desembarque de cada bote."""
    lote = s.get(Lote, lote_id)
    if lote is None or lote.estado != EstadoLote.ABIERTO:
        raise ValueError("Esta venta conjunta ya no está abierta.")
    if not comprador_id:
        raise ValueError("Indica a quién se vendió.")
    if not precio_venta or precio_venta < lote.precio_minimo:
        raise ValueError(f"El precio acordado es como mínimo {analytics.clp(lote.precio_minimo)}/kg. "
                         "Bajo eso no se vende (lo decidieron los botes al sumarse).")
    aportes = s.exec(select(LoteAporte).where(LoteAporte.lote_id == lote_id)).all()
    if not aportes:
        raise ValueError("No hay botes sumados a esta venta.")
    lote.estado, lote.comprador_id, lote.precio_venta, lote.cerrado_por = (
        EstadoLote.VENDIDO, comprador_id, int(precio_venta), quien)
    nota = f"Venta conjunta #{lote.id}"
    for a in aportes:
        d = s.exec(select(Desembarque).where(
            Desembarque.fecha == lote.fecha, Desembarque.embarcacion_id == a.embarcacion_id,
            Desembarque.especie_id == lote.especie_id, Desembarque.precio_kg == None)).first()  # noqa: E711
        if d is None:
            d = Desembarque(fecha=lote.fecha, embarcacion_id=a.embarcacion_id, especie_id=lote.especie_id,
                            kg=a.kg, origen=Origen.PESADO, registrado_por=nota)
        d.precio_kg, d.comprador_id = int(precio_venta), comprador_id
        if d.calidad == Calidad.OK:
            d.notas_calidad = nota
        s.add(d)
    s.add(lote)
    s.commit()
    s.refresh(lote)
    return resumen(s, lote)


def cancelar(s: Session, lote_id: int, quien: str = "") -> Lote:
    lote = s.get(Lote, lote_id)
    if lote is None or lote.estado != EstadoLote.ABIERTO:
        raise ValueError("Solo se puede cancelar una venta abierta.")
    lote.estado, lote.cerrado_por = EstadoLote.CANCELADO, quien
    s.add(lote)
    s.commit()
    return lote
