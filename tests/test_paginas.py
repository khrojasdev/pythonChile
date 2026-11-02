"""Pruebas de interfaz: un usuario simulado recorre la app con cada perfil."""
from nicegui import ui
from nicegui.testing import User

PAGINAS = {
    "pescador": ["/inicio", "/registro", "/pendientes", "/salir", "/precio", "/mis-numeros", "/clima", "/avisos"],
    "registradora": ["/inicio", "/registro", "/tierra", "/pendientes", "/personas", "/cuaderno", "/precio"],
    "sindicato": ["/inicio", "/revision", "/informes", "/aporte-tierra", "/cuotas", "/embarcaciones", "/avisos",
                  "/precio", "/limites"],
}


async def entrar(user: User, rol: str):
    await user.open("/ingresar")
    if rol == "pescador":
        sel = user.find(marker="sel-bote").elements.pop()
        sel.set_value(next(iter(sel.options)))
        user.find(marker="entrar-pescador").click()
    else:
        user.find(marker=f"perfil-{rol}").click()
        user.find(marker=f"pin-{rol}").type("0000" if rol == "registradora" else "1234")
        user.find(marker=f"entrar-{rol}").click()
    await user.should_see("Cambiar de perfil")


async def test_portada_publica(user: User):
    await user.open("/")
    await user.should_see("Noticias de pesca")
    await user.should_see("Avisos de la directiva")
    await user.should_see(marker="boton-ingresar")


async def test_sin_perfil_no_entra(user: User):
    await user.open("/revision")
    await user.should_see("¿Con qué perfil entras?")


async def test_pin_incorrecto(user: User):
    await user.open("/ingresar")
    user.find(marker="perfil-sindicato").click()
    user.find(marker="pin-sindicato").type("9999")
    user.find(marker="entrar-sindicato").click()
    await user.should_see("PIN incorrecto")


async def test_cada_perfil_ve_su_menu(user: User):
    for rol, paginas in PAGINAS.items():
        await entrar(user, rol)
        for ruta in paginas:
            await user.open(ruta)
            await user.should_see("Cambiar de perfil")
        await user.open("/")


async def test_pescador_no_ve_paginas_de_directiva(user: User):
    await entrar(user, "pescador")
    await user.should_see("Mi día")
    await user.should_not_see("Revisión de datos")
    await user.open("/revision")
    await user.should_see("¿Con qué perfil entras?")


async def test_pescador_registra_y_recibe_veredicto(user: User):
    await entrar(user, "pescador")
    await user.open("/registro")
    user.find(marker="especie-Merluza").click()
    numeros = {n.props.get("label"): n for n in user.find(ui.number).elements}
    numeros["Litros de combustible"].set_value(55)
    numeros["Kilos"].set_value(90)
    numeros["Precio $/kg"].set_value(1000)
    user.find("Guardar desembarque").click()
    await user.should_see("Desembarque guardado")
    await user.should_see("Está bajo lo normal")


async def test_registradora_guarda_trabajo_en_tierra(user: User):
    await entrar(user, "registradora")
    await user.open("/tierra")
    persona = next(s for s in user.find(ui.select).elements if s.props.get("label") == "Persona")
    persona.set_value(next(iter(persona.options)))
    numeros = list(user.find(ui.number).elements)
    numeros[0].set_value(800)
    numeros[1].set_value(5)
    await user.should_see("Este trabajo vale aprox.")
    user.find("Guardar trabajo").click()
    await user.should_see("Guardado")


async def test_directiva_aprueba_desde_la_pantalla(user: User):
    from sqlmodel import select
    from app.db import sesion
    from app.models import Calidad, Desembarque
    with sesion() as s:
        d = s.exec(select(Desembarque).where(Desembarque.calidad == Calidad.ADVERTENCIA)
                   .order_by(Desembarque.fecha.desc())).first()
    await entrar(user, "sindicato")
    await user.open("/revision")
    user.find(marker=f"aprobar-{d.id}").click()
    await user.should_see("Aprobado")
    with sesion() as s:
        assert s.get(Desembarque, d.id).calidad == Calidad.OK


async def test_directiva_publica_aviso(user: User):
    await entrar(user, "sindicato")
    await user.open("/avisos")
    user.find(marker="aviso-titulo").type("Corte de agua en el muelle")
    user.find(marker="aviso-cuerpo").type("El martes no habrá agua de 9 a 13 h.")
    user.find(marker="aviso-publicar").click()
    await user.should_see("Aviso publicado")
    await user.should_see("Corte de agua en el muelle")
