import psycopg2

def prueba_final():
    print("🚀 Iniciando intento de conexión...")
    
    try:
        # Usamos una "Connection String" (todo en una línea)
        # Esto fuerza la codificación a UTF-8 y usa la IP directa.
        conn = psycopg2.connect(
            "dbname=runner_app_db user=postgres password=1234 host=127.0.0.1 port=5432 client_encoding=utf8"
        )
        
        print("\n" + "✅" * 10)
        print("¡CONEXIÓN EXITOSA!")
        print("La base de datos y Python ya están conectados.")
        print("✅" * 10 + "\n")
        conn.close()
        
    except Exception as e:
        print("\n❌ FALLÓ LA CONEXIÓN:")
        print(e)

if __name__ == "__main__":
    prueba_final()