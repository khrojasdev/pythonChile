# 🌊 Mar Adentro

Plataforma para una caleta de pesca artesanal — **Caso 6, Hackatón Python Chile · Duoc UC Valparaíso**.
Hecha 100 % en Python: NiceGUI (interfaz), SQLModel (datos y validación), pandas (análisis) y fpdf2 (PDF).

> Todos los datos son **ficticios**, incluido el estado del mar.

## Qué decisión ayuda a tomar

| Pantalla | Pregunta que responde | Quién la usa |
|---|---|---|
| 🛶 Anotar desembarque | ¿Cuánto pesqué y a cuánto vendí? (y al guardar: **¿fue buen precio?**) | Pescador o registradora, **en tierra al llegar** |
| 💲 ¿Es buen precio? | ¿La oferta del comprador está bajo lo normal? ¿Quién paga mejor? | Pescador |
| 🚦 ¿Salgo mañana? | Mar (simulado) + veda + costo de combustible vs ganancia típica | Pescador |
| 📒 Mis números | ¿Cuántas salidas no cubrieron costos? (solo los ve el dueño) | Pescador |
| 🧺 Trabajo en tierra | Encarnado, fileteo, venta: **valorizado en $** | Registradora |
| 🧹 Revisar datos | Datos dudosos marcados, corrección y digitalización de cuadernos (CSV) | Registradora / sindicato |
| 📊 Panel · 📄 Informe PDF | Totales de la caleta sin nombres, listo para postular a fondos | Sindicato |
| ℹ️ Límites y decisiones | Qué NO se debe concluir de los datos, privacidad | Todos (y el jurado) |

## Correr en local (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Abrir <http://localhost:8080>. La primera vez se generan los datos ficticios solos (≈3 s).
Para regenerarlos: `python -m app.seed`. Para abrirlo desde el celular en la misma red wifi: `http://IP-DEL-PC:8080`.

PIN de demo: registradora **0000**, sindicato **1234**. El pescador entra eligiendo su embarcación.

## Desplegar en Render

1. Subir esta carpeta a un repo de GitHub.
2. En Render: **New → Blueprint** y elegir el repo (usa `render.yaml`).
   O **New → Web Service**: build `pip install -r requirements.txt`, start `python -m app.main`.
3. Listo. En el plan gratis la app se duerme tras unos minutos sin uso (la primera visita tarda ~1 min)
   y el disco se borra en cada reinicio: por eso la app regenera los datos ficticios al arrancar.
   Para datos persistentes, crear un PostgreSQL en Render y poner su URL en `DATABASE_URL`.

## Pruebas

```bash
pytest -q
```
24 pruebas: reglas de validación, analítica, importación de cuadernos y recorridos de interfaz por rol.

## Estructura

```
app/
├── main.py         arranque
├── config.py       parámetros de la caleta (tarifas, umbrales, PIN)
├── models.py       tablas (SQLModel)
├── validation.py   reglas de calidad: ok / advertencia / error
├── analytics.py    precio de referencia, semáforo, panel, cuotas
├── importar.py     digitalizar cuadernos desde CSV
├── reports.py      informe PDF
├── seed.py         datos ficticios con errores sembrados a propósito
├── ui_comun.py     estilos, encabezado, permisos por rol
└── pages/          una pantalla por archivo
tests/
```

## Decisiones clave (para el pitch)

- **El registro se hace en tierra**, no en el mar: no hay señal ni manos secas.
- **Origen del dato** en cada registro: pesado, estimado o reconstruido de cuaderno.
- **Nada se corrige a escondidas**: lo dudoso se marca y alguien lo revisa; lo erróneo no entra a los cálculos.
- **Estadística simple con n visible** en vez de ML: con datos ficticios un modelo solo aprendería lo inventado.
- **Privacidad por rol**: el pescador ve lo suyo; el sindicato, totales; terceros, un PDF sin nombres ni zonas.
- **No se registran zonas de pesca**, para no empujar a todos al mismo lugar.

## Guion de demo (≈ 90 s del pitch)

1. Entrar como pescador → **Anotar desembarque**: Merluza, 90 kg, $1.300 → aparece en rojo *"Está bajo lo normal"* y quién paga mejor.
2. **¿Salgo mañana?** → semáforo con sus razones y "lo que NO considera".
3. Cambiar a sindicato → **Panel**: "1 de cada 4 salidas no cubre costos", trabajo en tierra valorizado, cuota de jibia sobre 80 %.
4. **Revisar datos**: un registro con 551 kg marcado → corregir. Subir la plantilla CSV de un cuaderno → reporte fila por fila.
5. **Descargar PDF** para el fondo.
