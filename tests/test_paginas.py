"""Pruebas de interfaz: un usuario simulado recorre las páginas de cada rol."""
from nicegui import ui
from nicegui.testing import User

PAGINAS_SINDICATO = ["/panel", "/informe", "/calidad", "/tierra", "/precio", "/salir", "/limites"]


async def test_sin_rol_se_ve_eleccion(user: User):
    await user.open("/")
    await user.should_see("¿Quién eres?")
    await user.open("/panel")                   # página protegida: vuelve al inicio
    await user.should_see("¿Quién eres?")


async def test_pin_incorrecto(user: User):
    await user.open("/")
    user.find(marker="pin-sindicato").type("9999")
    user.find(marker="entrar-sindicato").click()
    await user.should_see("PIN incorrecto")


async def test_sindicato_recorre_paginas(user: User):
    await user.open("/")
    user.find(marker="pin-sindicato").type("1234")
    user.find(marker="entrar-sindicato").click()
    await user.open("/")
    await user.should_see("Panel de la caleta")
    for ruta in PAGINAS_SINDICATO:
        await user.open(ruta)
    await user.open("/panel")
    await user.should_see("Cuotas del año")
    await user.open("/salir")
    await user.should_see("¿Qué NO considera este semáforo?")
    await user.open("/calidad")
    await user.should_see("Digitalizar un cuaderno antiguo")


async def test_registradora_anota_trabajo_en_tierra(user: User):
    await user.open("/")
    user.find(marker="pin-registradora").type("0000")
    user.find(marker="entrar-registradora").click()
    await user.open("/tierra")
    await user.should_see("Trabajo en tierra")
    await user.open("/registro")
    await user.should_see("Otra especie")


async def test_pescador_solo_ve_lo_suyo(user: User):
    await user.open("/")
    sel = user.find(marker="sel-bote").elements.pop()
    sel.set_value(next(iter(sel.options)))
    user.find(marker="entrar-pescador").click()
    await user.open("/")
    await user.should_see("Mis números")
    await user.should_not_see("Panel de la caleta")
    await user.open("/mis-numeros")
    await user.should_see("solo los ves tú")
    await user.open("/salir")
    await user.should_see("Mañana")
    await user.open("/panel")                   # no tiene permiso: vuelve al inicio
    await user.should_see("Mis números")


async def test_pescador_registra_desembarque_y_recibe_veredicto(user: User):
    await user.open("/")
    sel = user.find(marker="sel-bote").elements.pop()
    sel.set_value(next(iter(sel.options)))
    user.find(marker="entrar-pescador").click()
    await user.should_see("Mis números")
    await user.open("/registro")
    especie = next(t for t in user.find(ui.toggle).elements if "Merluza" in str(t.options))
    especie.set_value(1)                                    # Merluza
    numeros = {n.props.get("label"): n for n in user.find(ui.number).elements}
    numeros["⛽ Litros combustible"].set_value(55)
    numeros["Kilos"].set_value(90)
    numeros["Precio $/kg"].set_value(1000)                  # bajo lo normal
    user.find("💾 Guardar").click()
    await user.should_see("Guardado")
    await user.should_see("Está bajo lo normal")


async def test_registradora_guarda_trabajo_en_tierra(user: User):
    await user.open("/")
    user.find(marker="pin-registradora").type("0000")
    user.find(marker="entrar-registradora").click()
    await user.should_see("Revisar datos")
    await user.open("/tierra")
    persona = next(s for s in user.find(ui.select).elements if s.props.get("label") == "Persona")
    persona.set_value(next(iter(persona.options)))
    numeros = list(user.find(ui.number).elements)
    numeros[0].set_value(800)
    numeros[1].set_value(5)
    await user.should_see("Este trabajo vale aprox.")
    user.find("💾 Guardar").click()
    await user.should_see("Guardado")
