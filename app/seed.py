"""Generador de datos FICTICIOS para la caleta.

Crea 12 meses de historia para 41 embarcaciones, ~60 personas en tierra,
compradores y estado del mar. Además mete errores y huecos A PROPÓSITO
(kilos mal tipeados, precios faltantes, duplicados, registros en veda) para
mostrar cómo la plataforma los detecta.

Uso:  python -m app.seed            (regenera la base)
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import delete, insert
from sqlmodel import select

from app import config
from app.db import crear_tablas, engine, sesion
from app.models import (Aviso, Meta, Calidad, Comprador, CondicionMar, Desembarque, Embarcacion,
                        Especie, Origen, PersonaTierra, TipoComprador, TipoTrabajo,
                        TrabajoTierra)
from app.validation import ReferenciaPrecio, validar_desembarque, validar_trabajo_tierra

SEMILLA = 42
DIAS_HISTORIA = 365

# nombre, icono, kg_max, precio_min, precio_max, precio_base, kg_tipico, veda, cuota, meses fuertes
ESPECIES = [
    ("Merluza", "🐟", 350, 900, 3500, 1900, 110, (9, 9), 190_000, [10, 11, 12, 1, 2, 3, 4]),
    ("Reineta", "🐠", 300, 1200, 4500, 2600, 80, None, None, [11, 12, 1, 2, 3]),
    ("Jibia", "🦑", 900, 400, 1800, 850, 320, None, 350_000, [3, 4, 5, 6, 7, 8]),
    ("Congrio", "🐍", 120, 2500, 7000, 4300, 35, None, None, list(range(1, 13))),
    ("Corvina", "🐡", 150, 2000, 6500, 3800, 45, None, None, [12, 1, 2, 3]),
    ("Sierra", "🐬", 200, 1000, 3500, 2000, 70, None, None, [5, 6, 7, 8, 9]),
]

NOMBRES_BOTE = ["Don Lucho", "Gaviota", "Estrella del Sur", "Santa Rosa", "Mar Bravo",
                "Pelícano", "La Chascona", "Bendición", "Cormorán", "Rayo de Luna",
                "San Pedro", "Lobito", "Marejada", "Albatros", "Perla"]

COMPRADORES = [
    ("Intermediario Norte", TipoComprador.INTERMEDIARIO),
    ("Distribuidora El Ancla", TipoComprador.INTERMEDIARIO),
    ("Camiones Costa", TipoComprador.INTERMEDIARIO),
    ("Pescadería La Ola", TipoComprador.PESCADERIA),
    ("Pescadería Mercado Puerto", TipoComprador.PESCADERIA),
    ("Restaurante El Muelle", TipoComprador.RESTAURANTE),
    ("Picada Doña Juana", TipoComprador.RESTAURANTE),
    ("Venta en caleta", TipoComprador.VENTA_DIRECTA),
]
FACTOR_COMPRADOR = {TipoComprador.INTERMEDIARIO: 0.86, TipoComprador.PESCADERIA: 1.0,
                    TipoComprador.RESTAURANTE: 1.08, TipoComprador.VENTA_DIRECTA: 1.05}


def _ola_estacional(d: date) -> float:
    # invierno (jun-ago) con más oleaje
    return 1.55 + 0.55 * math.cos((d.timetuple().tm_yday - 200) / 365 * 2 * math.pi)


def generar(hoy: date | None = None, verbose: bool = True) -> None:
    hoy = hoy or date.today()
    rng = np.random.default_rng(SEMILLA)
    fake = Faker("es_CL")
    Faker.seed(SEMILLA)

    crear_tablas()
    with sesion() as s:
        for modelo in (Aviso, TrabajoTierra, Desembarque, CondicionMar, PersonaTierra,
                       Comprador, Embarcacion, Especie):
            s.exec(delete(modelo))
        s.commit()

        # ----------------------------------------------------- catálogos
        especies = []
        for nom, ico, kgmax, pmin, pmax, *_rest in ESPECIES:
            veda, cuota = _rest[2], _rest[3]
            e = Especie(nombre=nom, icono=ico, kg_max_salida=kgmax, precio_min=pmin,
                        precio_max=pmax, veda_mes_inicio=veda[0] if veda else None,
                        veda_mes_fin=veda[1] if veda else None, cuota_anual_kg=cuota)
            s.add(e)
            especies.append(e)

        botes = []
        for i in range(41):
            base = NOMBRES_BOTE[i % len(NOMBRES_BOTE)]
            nombre = base if i < len(NOMBRES_BOTE) else f"{base} {['II', 'III', 'IV'][i // len(NOMBRES_BOTE) - 1]}"
            b = Embarcacion(nombre=nombre, matricula=f"FIC-{1000 + i}",
                            patron=fake.first_name_male() + " " + fake.last_name(),
                            litros_por_salida=float(rng.integers(35, 95)))
            s.add(b)
            botes.append(b)

        compradores = [Comprador(nombre=n, tipo=t) for n, t in COMPRADORES]
        s.add_all(compradores)

        personas = []
        roles = ([TipoTrabajo.ENCARNADO] * 26 + [TipoTrabajo.FILETEO] * 18 +
                 [TipoTrabajo.VENTA] * 10 + [TipoTrabajo.LIMPIEZA] * 6)
        for rol in roles:
            nombre = (fake.first_name_female() if rng.random() < 0.85 else fake.first_name_male())
            p = PersonaTierra(nombre=f"{nombre} {fake.last_name()}", rol_principal=rol)
            s.add(p)
            personas.append(p)
        s.commit()
        for obj in especies + botes + compradores + personas:
            s.refresh(obj)

        # ----------------------------------------------------- estado del mar
        inicio = hoy - timedelta(days=DIAS_HISTORIA)
        dias = [inicio + timedelta(days=k) for k in range(DIAS_HISTORIA)]
        mar = {}
        filas_mar = []
        for d in dias + [hoy + timedelta(days=k) for k in range(0, 4)]:
            ola = max(0.4, rng.normal(_ola_estacional(d), 0.55))
            viento = max(2, rng.normal(8 + ola * 5, 4))
            mar[d] = (round(ola, 1), round(viento))
            filas_mar.append(dict(fecha=d, ola_m=round(ola, 1), viento_nudos=round(viento),
                                  es_pronostico=d >= hoy))
        s.execute(insert(CondicionMar), filas_mar)

        # ----------------------------------------------------- precios diarios (latentes)
        log_dev = {e.nombre: 0.0 for e in especies}
        precio_dia: dict[tuple[str, date], float] = {}
        for d in dias:
            for nom, *_x in ESPECIES:
                # caminata aleatoria con reversión a la media: genera meses con
                # variaciones de hasta ~2,3 veces, como describe el caso
                log_dev[nom] = 0.85 * log_dev[nom] + rng.normal(0, 0.07)
                precio_dia[(nom, d)] = math.exp(log_dev[nom])

        # ----------------------------------------------------- salidas y capturas
        info = {e[0]: e for e in ESPECIES}
        filas_d, filas_t = [], []
        corte_digital = hoy - timedelta(days=60)   # antes: cuadernos; después: app
        for d in dias:
            ola, viento = mar[d]
            p_salir = 0.04 if ola >= config.OLA_ROJO_M else (0.35 if ola >= config.OLA_AMARILLO_M else 0.6)
            if d.weekday() == 6:
                p_salir *= 0.4
            disponibles = [e for e in especies if d.month in info[e.nombre][9]]
            salidas_hoy = []
            for b in botes:
                if rng.random() > p_salir:
                    continue
                n_esp = 1 if rng.random() < 0.7 else 2
                objetivo = list(rng.choice(disponibles, size=min(n_esp, len(disponibles)), replace=False))
                if d.month == 9 and rng.random() < 0.03:      # alguien anotó merluza en veda
                    objetivo = [especies[0]]
                salidas_hoy.append((b, objetivo))

            # oferta del día baja el precio (más botes = precio más bajo)
            presion = len(salidas_hoy) / 41
            for b, objetivo in salidas_hoy:
                origen = (Origen.CUADERNO if rng.random() < 0.9 else Origen.ESTIMADO) if d < corte_digital \
                    else (Origen.PESADO if rng.random() < 0.7 else Origen.ESTIMADO)
                litros = round(b.litros_por_salida * rng.normal(1, 0.12), 1)
                for k, e in enumerate(objetivo):
                    _, _, kgmax, pmin, pmax, pbase, kgtip, *_ = info[e.nombre]
                    clima = max(0.25, 1.08 - 0.25 * ola)
                    kg = 0.0 if rng.random() < 0.07 else round(float(rng.lognormal(math.log(kgtip * clima), 0.55)), 1)
                    comp = compradores[int(rng.choice(len(compradores), p=[.2, .17, .15, .14, .1, .08, .06, .1]))]
                    precio = pbase * precio_dia[(e.nombre, d)] * (1.08 - 0.2 * presion) \
                        * FACTOR_COMPRADOR[comp.tipo] * rng.normal(1, 0.03)
                    precio = int(round(min(max(precio, pmin * 0.8), pmax * 1.1) / 10) * 10)
                    fila = dict(fecha=d, embarcacion_id=b.id, especie_id=e.id, kg=kg,
                                precio_kg=precio if kg > 0 else None,
                                comprador_id=comp.id if kg > 0 else None,
                                litros_combustible=litros if k == 0 else None,
                                precio_litro=config.PRECIO_LITRO_DEFECTO + int(rng.integers(-60, 60)) if k == 0 else None,
                                costo_carnada=int(rng.integers(8, 22)) * 1000 if k == 0 else None,
                                origen=origen, registrado_por="carga histórica")
                    # ---- errores y huecos intencionales
                    x = rng.random()
                    if kg > 0 and x < 0.02:
                        fila["kg"] = kg * 10                     # se corrió la coma
                    elif kg > 0 and x < (0.12 if origen == Origen.CUADERNO else 0.04):
                        fila["precio_kg"] = None                 # precio no anotado
                    elif x < 0.125 and origen == Origen.CUADERNO:
                        fila["kg"] = None                        # página mojada
                    if origen == Origen.CUADERNO and k == 0 and rng.random() < 0.1:
                        fila["litros_combustible"] = None
                    filas_d.append(fila)
                    if rng.random() < 0.008:
                        filas_d.append(dict(fila))               # duplicado

            # ----- trabajo en tierra: depende de cuántos botes salieron
            n_sal = len(salidas_hoy)
            for p in personas:
                if n_sal == 0 and p.rol_principal != TipoTrabajo.LIMPIEZA:
                    continue
                if rng.random() > min(0.9, 0.25 + n_sal / 30):
                    continue
                if p.rol_principal == TipoTrabajo.ENCARNADO:
                    horas = round(float(rng.normal(5.5, 1.2)), 1)
                    cantidad = int(horas * rng.normal(160, 25))
                elif p.rol_principal == TipoTrabajo.FILETEO:
                    horas = round(float(rng.normal(4.5, 1.3)), 1)
                    cantidad = round(horas * float(rng.normal(14, 3)), 1)
                else:
                    horas = round(float(rng.normal(5, 1.5)), 1)
                    cantidad = horas
                horas = max(horas, 0.5)
                filas_t.append(dict(fecha=d, persona_id=p.id, tipo=p.rol_principal,
                                    cantidad=max(cantidad, 0), horas=horas,
                                    registrado_por="carga histórica"))

        # ----------------------------------------------------- validación de todo
        df = pd.DataFrame(filas_d)
        df["mes"] = pd.to_datetime(df["fecha"]).dt.to_period("M")
        ref = (df.dropna(subset=["precio_kg"]).groupby(["especie_id", "mes"])["precio_kg"]
               .agg(n="count", mediana="median",
                    mad=lambda x: float(np.median(np.abs(x - np.median(x))))))
        esp_por_id = {e.id: e for e in especies}
        vistos = set()
        for fila, mes in zip(filas_d, df["mes"]):
            clave = (fila["fecha"], fila["embarcacion_id"], fila["especie_id"], fila["kg"])
            r_ref = ref.loc[(fila["especie_id"], mes)] if (fila["especie_id"], mes) in ref.index else None
            res = validar_desembarque(
                fecha=fila["fecha"], especie=esp_por_id[fila["especie_id"]], kg=fila["kg"],
                precio_kg=fila["precio_kg"], litros=fila["litros_combustible"],
                referencia=ReferenciaPrecio(int(r_ref["n"]), r_ref["mediana"], r_ref["mad"]) if r_ref is not None else None,
                es_duplicado=clave in vistos, hoy=hoy)
            vistos.add(clave)
            fila["calidad"], fila["notas_calidad"] = res.calidad, res.texto
        for fila in filas_t:
            res = validar_trabajo_tierra(fecha=fila["fecha"], cantidad=fila["cantidad"],
                                         horas=fila["horas"], hoy=hoy)
            fila["calidad"], fila["notas_calidad"] = res.calidad, res.texto

        s.execute(insert(Desembarque), filas_d)
        s.execute(insert(TrabajoTierra), filas_t)
        _avisos_demo(s, hoy)
        meta = s.get(Meta, "schema") or Meta(clave="schema", valor="")
        meta.valor = SCHEMA
        s.add(meta)
        s.commit()

    if verbose:
        print(f"Datos ficticios generados: {len(filas_d)} líneas de desembarque, "
              f"{len(filas_t)} registros de trabajo en tierra.")


SCHEMA = "2"   # súbelo cuando cambien las tablas: la base de demo se regenera sola


def _avisos_demo(s, hoy: date) -> None:
    from datetime import datetime, time, timezone
    avisos = [
        ("Asamblea de socios el jueves", "Revisaremos la postulación al fondo de equipamiento. "
         "Trae tus dudas sobre el registro de desembarques.", "reunion", True, 2),
        ("Cuota de jibia sobre el 80 %", "Queda poco margen para el resto del año. "
         "Coordinemos las salidas para no pasarnos.", "alerta", False, 4),
        ("Nueva balanza en el muelle", "Desde este mes se puede pesar la captura al llegar. "
         "Un dato pesado vale más que uno estimado.", "info", False, 9),
    ]
    for titulo, cuerpo, tipo, fijado, dias in avisos:
        s.add(Aviso(titulo=titulo, cuerpo=cuerpo, tipo=tipo, fijado=fijado,
                    publicado_en=datetime.combine(hoy - timedelta(days=dias), time(21, 30), tzinfo=timezone.utc)))


def asegurar_datos() -> None:
    """Si la base está vacía o es de una versión anterior, genera los datos de demo."""
    from sqlalchemy import inspect
    from sqlmodel import SQLModel
    insp = inspect(engine)
    vieja = False
    if insp.has_table("desembarque"):
        columnas = {c["name"] for c in insp.get_columns("desembarque")}
        vieja = "revisado_por" not in columnas
    if vieja:   # esquema anterior: se borra y se rehace (solo datos ficticios)
        SQLModel.metadata.drop_all(engine)
    crear_tablas()
    with sesion() as s:
        meta = s.get(Meta, "schema")
        if s.exec(select(Especie)).first() is None or meta is None or meta.valor != SCHEMA:
            generar()


if __name__ == "__main__":
    generar()
