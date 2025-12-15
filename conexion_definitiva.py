import psycopg2

def conectar():
    print("🚀 Conectando a 'running_db'...")
    
    try:
        # AQUÍ ESTABA EL ERROR: Hemos cambiado 'dbname' al nombre real
        conn = psycopg2.connect(
            "dbname=running_db user=runner_user password=1234 host=127.0.0.1 port=5432 client_encoding=utf8"
        )
        print("\n" + "✅" * 15)
        print(" ¡CONEXIÓN EXITOSA! ")
        print(" Python ya está dentro de 'running_db'.")
        print("✅" * 15 + "\n")
        conn.close()

    except Exception as e:
        print("\n❌ FALLO:")
        print(e)

if __name__ == "__main__":
    conectar()