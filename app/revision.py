"""Reglas de la revisión de datos (separadas de la interfaz para poder probarlas).

Acciones de la directiva sobre un registro marcado:
- aprobar   -> el dato era correcto: pasa a OK y queda constancia de quién lo aprobó.
- corregir  -> se cambian kilos/precio, se vuelve a validar y, si pasa, queda OK.
- rechazar  -> el dato no sirve: queda RECHAZADO y sale de todos los cálculos.
- deshacer  -> vuelve al estado que tenía antes de la revisión.
Nada se borra: el registro y el motivo original quedan guardados.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.models import Calidad, Desembarque, Especie
from app.validation import validar_desembarque


class RevisionError(ValueError):
    pass


def _marcar(d: Desembarque, nueva: Calidad, quien: str, nota: str) -> None:
    if d.calidad_original is None:
        d.calidad_original = d.calidad.value if isinstance(d.calidad, Calidad) else str(d.calidad)
    d.calidad = nueva
    d.revisado_por = quien
    d.revisado_en = datetime.now(timezone.utc)
    antes = d.notas_calidad.split(" || Antes: ")[-1] if " || Antes: " in d.notas_calidad else d.notas_calidad
    d.notas_calidad = f"{nota} || Antes: {antes}" if antes else nota


def aprobar(s: Session, id_: int, quien: str) -> Desembarque:
    d = s.get(Desembarque, id_)
    if d is None:
        raise RevisionError("El registro ya no existe")
    if d.calidad == Calidad.ERROR:
        raise RevisionError("Un registro con error no se puede aprobar tal cual: corrígelo o recházalo")
    _marcar(d, Calidad.OK, quien, f"Aprobado por {quien}")
    s.add(d)
    s.commit()
    s.refresh(d)
    return d


def corregir(s: Session, id_: int, quien: str, kg: Optional[float], precio: Optional[float]) -> tuple[Desembarque, str]:
    """Devuelve (registro, motivo). Si el motivo no es vacío, la corrección sigue con error y NO se guarda."""
    d = s.get(Desembarque, id_)
    if d is None:
        raise RevisionError("El registro ya no existe")
    res = validar_desembarque(fecha=d.fecha, especie=s.get(Especie, d.especie_id), kg=kg,
                              precio_kg=precio, litros=d.litros_combustible)
    if res.calidad == Calidad.ERROR:
        s.rollback()
        return d, res.texto
    cambios = []
    if kg != d.kg:
        cambios.append(f"kg {d.kg} → {kg}")
    if (int(precio) if precio else None) != d.precio_kg:
        cambios.append(f"precio {d.precio_kg} → {int(precio) if precio else None}")
    d.kg = kg
    d.precio_kg = int(precio) if precio else None
    _marcar(d, Calidad.OK, quien, f"Corregido por {quien}" + (f" ({', '.join(cambios)})" if cambios else ""))
    s.add(d)
    s.commit()
    s.refresh(d)
    return d, ""


def rechazar(s: Session, id_: int, quien: str, motivo: str = "") -> Desembarque:
    d = s.get(Desembarque, id_)
    if d is None:
        raise RevisionError("El registro ya no existe")
    _marcar(d, Calidad.RECHAZADO, quien, f"Rechazado por {quien}" + (f": {motivo}" if motivo else ""))
    s.add(d)
    s.commit()
    s.refresh(d)
    return d


def deshacer(s: Session, id_: int) -> Desembarque:
    d = s.get(Desembarque, id_)
    if d is None or d.calidad_original is None:
        raise RevisionError("Este registro no tiene una revisión que deshacer")
    d.calidad = Calidad(d.calidad_original)
    d.calidad_original = None
    d.revisado_por = ""
    d.revisado_en = None
    if " || Antes: " in d.notas_calidad:
        d.notas_calidad = d.notas_calidad.split(" || Antes: ")[-1]
    s.add(d)
    s.commit()
    s.refresh(d)
    return d
