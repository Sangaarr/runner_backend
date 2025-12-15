from database import get_db_connection

# --- FUNCIÓN 1: CREAR USUARIO (INSERT) ---
def crear_runner_prueba():
    # 1. Obtenemos la conexión
    conn = get_db_connection()
    if not conn:
        return

    try:
        # 2. Creamos un "cursor"
        cur = conn.cursor()

        # 3. Datos del nuevo usuario
        nuevo_runner = (
            "usuario1@email.com",   # email
            "pass_secreta_hash",    # password
            "RunnerVeloz",          # username
            "ACTIVA"                # estado_cuenta
        )

        # 4. Sentencia SQL
        sql = """
            INSERT INTO runner (email, password_hash, username, estado_cuenta)
            VALUES (%s, %s, %s, %s)
            RETURNING id_runner;
        """

        # 5. Ejecutamos
        print("⏳ Insertando usuario...")
        cur.execute(sql, nuevo_runner)
        
        # 6. Obtenemos ID
        id_generado = cur.fetchone()[0]
        
        # 7. Guardamos (Commit)
        conn.commit()
        
        print(f"✅ ¡Runner creado con éxito! Su ID es: {id_generado}")

        cur.close()
        conn.close()

    except Exception as e:
        print("❌ Error al insertar:", e)
        if conn:
            conn.rollback()

# --- FUNCIÓN 2: LEER USUARIOS (SELECT) ---
def ver_todos_los_runners():
    # 1. Obtenemos conexión
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        # 2. Ejecutamos la consulta
        cur.execute("SELECT id_runner, username, email, estado_cuenta FROM runner;")
        
        # 3. Recuperamos resultados
        runners = cur.fetchall()
        
        print("\n--- LISTA DE RUNNERS ---")
        for runner in runners:
            print(f"ID: {runner[0]} | Usuario: {runner[1]} | Email: {runner[2]} | Estado: {runner[3]}")
        print("------------------------\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print("❌ Error al leer:", e)


# --- BLOQUE DE EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    # Comenta o descomenta la línea que quieras usar:

    # crear_runner_prueba()       # <--- Mantenla comentada (#) si ya creaste el usuario antes
    ver_todos_los_runners()       # <--- Esta es la que se ejecutará ahora