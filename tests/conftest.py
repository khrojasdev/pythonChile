import os

# Base de datos aparte para las pruebas (se genera sola con datos ficticios)
os.environ["DATABASE_URL"] = "sqlite:///data/test.db"

pytest_plugins = ["nicegui.testing.user_plugin"]
