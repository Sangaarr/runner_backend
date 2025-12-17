import os
import psycopg2

# --- CONFIGURACIÓN LOCAL (Tus datos actuales) ---
# Estos se usarán cuando trabajes en tu PC
DB_HOST_LOCAL = "127.0.0.1"
DB_NAME_LOCAL = "running_db"
DB_USER_LOCAL = "runner_user"  # <--- Tu usuario
DB_PASS_LOCAL = "1234"         # <--- Tu contraseña

def get_db_connection():
    try:
        # 1. INTENTAMOS CONECTARNOS A LA NUBE (Render)
        # Render nos dará esta dirección automáticamente cuando subamos el código
        database_url = os.getenv("INTERNAL_DATABASE_URL")
        
        if database_url:
            # Estamos en la Nube ☁️
            conn = psycopg2.connect(database_url)
        else:
            # 2. SI NO HAY NUBE, NOS CONECTAMOS AL PC (Local) 💻
            conn = psycopg2.connect(
                host=DB_HOST_LOCAL,
                database=DB_NAME_LOCAL,
                user=DB_USER_LOCAL,
                password=DB_PASS_LOCAL,
                client_encoding="utf8"
            )
        return conn
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {e}")
        return None