"""Parámetros de la caleta. Todos referenciales y ficticios: el sindicato los ajusta."""
import os

from app.models import TipoTrabajo

NOMBRE_CALETA = "Caleta Punta Ficticia"

# Base de datos: SQLite local por defecto. En Render se puede usar DATABASE_URL (Postgres).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/mar_adentro.db")
if DATABASE_URL.startswith("postgres://"):            # formato que entrega Render
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Combustible
PRECIO_LITRO_DEFECTO = 1150          # CLP por litro (ficticio)

# Valorización del trabajo en tierra (tarifas referenciales, CLP)
TARIFA_TIERRA = {
    TipoTrabajo.ENCARNADO: ("anzuelos", 12),     # $ por anzuelo encarnado
    TipoTrabajo.FILETEO: ("kg", 450),            # $ por kg fileteado
    TipoTrabajo.VENTA: ("horas", 3500),          # $ por hora
    TipoTrabajo.LIMPIEZA: ("horas", 3000),       # $ por hora
}

# Semáforo de salida
OLA_ROJO_M = 2.5          # sobre esto no se recomienda salir
OLA_AMARILLO_M = 1.8
VIENTO_ROJO_NUDOS = 25
MARGEN_AMARILLO = 0.20    # margen esperado < 20 % del costo -> amarillo

# Estadística: mínimo de datos para mostrar un número como "confiable"
N_MINIMO_CONFIABLE = 8
DIAS_REFERENCIA = 30

# PINs de demo para entrar por rol (solo para la demostración)
PIN_SINDICATO = os.environ.get("PIN_SINDICATO", "1234")
PIN_REGISTRADORA = os.environ.get("PIN_REGISTRADORA", "0000")

STORAGE_SECRET = os.environ.get("STORAGE_SECRET", "mar-adentro-demo-cambiar")
