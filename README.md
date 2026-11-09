# 🌊 Mar Adentro

Plataforma para una caleta de pesca artesanal (Caso 6, Hackatón Python Chile, Duoc UC Valparaíso).
Hecha 100 % en Python: NiceGUI (interfaz), SQLModel (datos y validación), pandas (análisis), fpdf2 (PDF) y httpx (APIs).

> Los datos de la caleta son **ficticios**, como pide el caso. El clima y el oleaje vienen de Open-Meteo
> (API pública y gratuita) y las noticias del RSS de Google Noticias; si no hay internet, la app usa un
> mar simulado y novedades de demo, y lo dice en pantalla.

## Recorrido

- **Portada pública** (`/`): clima de hoy, pronóstico de 7 días con color según el oleaje, noticias de pesca
  y avisos de la directiva. El botón **Ingresar** lleva a elegir perfil.
- **Ingresar** (`/ingresar`): pescador (elige su bote), registradora o directiva (con PIN).
- Al entrar, cada perfil tiene un **menú lateral** con sus propias opciones:

| Pescador | Registradora | Directiva |
|---|---|---|
| Mi día (semáforo de mañana, clima, ventas pendientes) | Jornada de hoy (botes que llegaron, kg, pendientes) | Panel de la caleta |
| Anotar desembarque | Anotar desembarque (cualquier bote) | **Revisión de datos**: aprobar, corregir, rechazar, deshacer, en lote |
| Ventas por completar | Trabajo en tierra | Informes y descargas (PDF y CSV) |
| ¿Salgo mañana? (pronóstico real + vedas + costos) | Ventas por completar | Aporte en tierra por persona |
| ¿Es buen precio? | Personas en tierra | Vedas y cuotas (editables) |
| Mis números (descarga PDF/CSV) | Digitalizar cuaderno (hoja PDF para imprimir + CSV) | Embarcaciones |
| Clima y mar · Avisos | Pizarra de precios · Clima · Avisos | Precios · Clima · Publicar avisos |

PIN de demo: registradora **0000**, directiva **1234**.

### Funciones nuevas (versión 3)

| Función | Quién | Qué problema resuelve |
|---|---|---|
| **Venta conjunta** (`/ventas-conjuntas`) | Los tres perfiles | Un bote solo no negocia. Los botes juntan kilos de una especie con un precio mínimo; al cerrar la venta el pago se reparte por kilos y el precio queda anotado en el desembarque de cada bote. Muestra cuánto más se gana frente al intermediario. |
| **Aviso de zarpe** (`/zarpe`) y **En el mar ahora** (`/en-el-mar`) | Pescador / registradora y directiva | Saber quién está en el mar y avisar si alguien pasa 30 min de su hora de vuelta. No se registra la zona de pesca. No reemplaza el zarpe oficial. |
| **Dictado por voz** (en `/registro`) | Pescador y registradora | Con manos mojadas: «merluza noventa kilos a mil trescientos» llena el formulario. Usa el micrófono del navegador (Chrome) o se puede escribir la frase. |
| **Comprobante de trabajo en tierra** (`/comprobantes`) | Registradora y directiva | PDF por persona y periodo, con días, horas y valor estimado, para subsidios o cursos. |
| **¿Listos para postular a un fondo?** (en `/informes`) | Directiva | Revisa 6 requisitos con los datos reales y dice qué falta. |
| **Pizarra del muelle** (`/pizarra`) | Pública, sin ingresar | Para un televisor en la sede: precios de la semana, estado del mar, botes en el mar y ventas conjuntas abiertas. Se actualiza sola. |

## Correr en local (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Abrir <http://localhost:8080>. La base de demo se crea sola (≈3 s) y se regenera si cambia el esquema.
Para empezar de cero: `python -m app.seed`.

## Desplegar en Render

New → Blueprint → elegir el repo (usa `render.yaml`). En el plan gratis la app se duerme sin uso
(la primera visita tarda ~1 min) y el disco se borra al reiniciar: por eso regenera los datos de demo.

## Sobre el aviso de "sin conexión"

Pasaba porque cada página recalculaba todo con pandas y bloqueaba el servidor unos segundos.
Ahora los datos se guardan en caché y se invalidan solo cuando alguien guarda algo (≈0,1 s por página);
clima y noticias se cargan después de mostrar la página; y la reconexión espera 30 s antes de rendirse.

## Pruebas

```bash
pytest -q
```
33 pruebas: validación, analítica, revisión (aprobar/corregir/rechazar/deshacer), exportaciones,
parsers de clima y noticias, y recorridos de interfaz con cada perfil.

## Foto de portada

«Wiki Tour - Caleta Portales 01», de Nereidas, licencia CC BY-SA 3.0, en
[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Wiki_Tour_-_Caleta_Portales_01.JPG).
Se carga desde Wikimedia; si existe `app/static/caleta_portales.jpg`, se usa esa copia local.
