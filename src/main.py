from database import get_db_connection
import datetime

# --- 1. CREAR RUNNER (Ya la conoces) ---
def crear_runner_prueba():
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        # Intentamos crear un runner (si el email ya existe, fallará y saltará al except)
        nuevo_runner = ("runner2@email.com", "pass123", "FlashRunner", "ACTIVA")
        
        sql = """
            INSERT INTO runner (email, password_hash, username, estado_cuenta)
            VALUES (%s, %s, %s, %s)
            RETURNING id_runner;
        """
        cur.execute(sql, nuevo_runner)
        id_generado = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Runner creado. ID: {id_generado}")
        return id_generado
        
    except Exception as e:
        print(f"⚠️ Aviso: {e}")
        return None
    finally:
        if conn: conn.close()

# --- 2. CREAR EQUIPO (¡NUEVO!) ---
def crear_equipo_prueba():
    conn = get_db_connection()
    if not conn: return None

    try:
        cur = conn.cursor()
        
        # Datos del equipo
        nuevo_equipo = (
            "Liebres de Montaña",       # nombre
            "Grupo de trail running",   # descripcion
            "Madrid"                    # ciudad_base
        )
        
        sql = """
            INSERT INTO equipo (nombre, descripcion, ciudad_base)
            VALUES (%s, %s, %s)
            RETURNING id_equipo;
        """
        
        print("⏳ Creando equipo...")
        cur.execute(sql, nuevo_equipo)
        id_equipo = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ ¡Equipo creado! ID: {id_equipo}")
        cur.close()
        conn.close()
        return id_equipo

    except Exception as e:
        print("❌ Error al crear equipo:", e)
        conn.rollback()
        return None

# --- 3. UNIR RUNNER A EQUIPO (¡LA PRUEBA DE FUEGO!) ---
def unir_runner_a_equipo(id_runner, id_equipo):
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        
        # Datos para la tabla intermedia
        union = (
            id_runner,
            id_equipo,
            "Miembro",                  # rol
            datetime.datetime.now()     # fecha_union
        )
        
        sql = """
            INSERT INTO runner_equipo (id_runner, id_equipo, rol, fecha_union)
            VALUES (%s, %s, %s, %s);
        """
        
        print(f"⏳ Uniendo Runner {id_runner} al Equipo {id_equipo}...")
        cur.execute(sql, union)
        conn.commit()
        
        print(f"🔗 ¡ÉXITO! El Runner {id_runner} ahora es parte del Equipo {id_equipo}.")
        
        cur.close()
        conn.close()

    except Exception as e:
        print("❌ Error al unir:", e)
        conn.rollback()

# --- 4. VER TODO JUNTO ---
def ver_relaciones():
    conn = get_db_connection()
    if not conn: return
    
    cur = conn.cursor()
    # Esta consulta usa INNER JOIN para combinar tablas
    sql = """
        SELECT r.username, e.nombre, re.rol 
        FROM runner r
        JOIN runner_equipo re ON r.id_runner = re.id_runner
        JOIN equipo e ON re.id_equipo = e.id_equipo;
    """
    cur.execute(sql)
    resultados = cur.fetchall()
    
    print("\n--- RELACIONES (Quién está en qué equipo) ---")
    for fila in resultados:
        print(f"🏃 {fila[0]} pertenece a 🏆 {fila[1]} como ({fila[2]})")
    print("---------------------------------------------\n")
    conn.close()


# --- EJECUCIÓN ---
if __name__ == "__main__":
    # 1. Usamos el ID 1 que ya creaste antes (o creamos uno nuevo si quieres)
    mi_runner_id = 1 
    
    # 2. Creamos un equipo nuevo
    mi_equipo_id = crear_equipo_prueba()
    
    if mi_runner_id and mi_equipo_id:
        # 3. Probamos la relación
        unir_runner_a_equipo(mi_runner_id, mi_equipo_id)
        
        # 4. Vemos el resultado final
        ver_relaciones()