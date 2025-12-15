import psycopg2
from psycopg2 import OperationalError

def get_db_connection():
    """
    Establece y devuelve una conexión a la base de datos running_db.
    """
    try:
        conn = psycopg2.connect(
            "dbname=running_db user=runner_user password=1234 host=127.0.0.1 port=5432 client_encoding=utf8"
        )
        return conn
    except OperationalError as e:
        print(f"❌ Error al conectar a la base de datos: {e}")
        return None