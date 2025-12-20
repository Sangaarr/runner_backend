from fastapi import APIRouter, HTTPException, Depends
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual # <--- IMPORTANTE: Seguridad

# Creamos el router (el "pasillo" exclusivo para Logros)
router = APIRouter()

# --- FUNCIÓN LÓGICA (AUXILIAR - NO ES UN ENDPOINT) ---
# Esta función la llama 'capturas.py' automáticamente.
def verificar_y_otorgar_logros(id_runner: int, conn):
    """
    Revisa si el usuario merece un nuevo logro basado en sus estadísticas.
    Devuelve True si ha ganado algo, False si no.
    NOTA: Recibe 'conn' abierta para trabajar en la misma transacción.
    """
    try:
        cur = conn.cursor()
        
        # 1. Contamos cuántas capturas lleva este usuario en total
        cur.execute("SELECT COUNT(*) FROM captura_zona WHERE id_runner = %s", (id_runner,))
        total_capturas = cur.fetchone()[0]
        
        # 2. Definimos las reglas (ID del logro : Capturas necesarias)
        # ID 1 = Primeros Pasos, ID 2 = Conquistador, ID 3 = Rey de la Colina
        # Asegúrate de que estos IDs existen en tu tabla 'logro' en la DB
        reglas = {
            1: 1,
            2: 5,
            3: 10
        }
        
        nuevos_logros = []
        
        # 3. Comprobamos cada regla
        for id_logro, capturas_necesarias in reglas.items():
            if total_capturas == capturas_necesarias:
                # ¡Bingo! Ha alcanzado la cifra exacta.
                # Verificamos si YA lo tiene (para no dárselo doble)
                cur.execute("SELECT 1 FROM runner_logro WHERE id_runner = %s AND id_logro = %s", (id_runner, id_logro))
                if not cur.fetchone():
                    # No lo tiene, SE LO DAMOS
                    cur.execute("INSERT INTO runner_logro (id_runner, id_logro, fecha_obtenido) VALUES (%s, %s, NOW())", (id_runner, id_logro))
                    
                    # Creamos notificación
                    cur.execute("""
                        INSERT INTO notificacion (id_runner, tipo, titulo, mensaje, leida, fecha_hora) 
                        VALUES (%s, 'LOGRO', '¡Nueva Medalla!', 'Has desbloqueado un logro nuevo.', FALSE, NOW())
                    """, (id_runner,))
                    
                    nuevos_logros.append(id_logro)
        
        # Guardamos los cambios parciales (sin cerrar la conexión, eso lo hace quien nos llamó)
        conn.commit()
        cur.close()
        return len(nuevos_logros) > 0 # Retorna True si ganó algo
        
    except Exception as e:
        print(f"Error comprobando logros: {e}")
        return False

# --- ENDPOINTS (RUTAS WEB) ---

@router.get("/logros/mios")
def ver_mis_logros_privado(
    id_runner_autenticado: int = Depends(obtener_runner_actual) # <--- CANDADO DE SEGURIDAD
):
    """Muestra las medallas del usuario LOGUEADO (usando el Token)"""
    return ver_logros_de_usuario(id_runner_autenticado)


@router.get("/runner/{id_runner}/logros")
def ver_logros_de_usuario(id_runner: int):
    """Muestra las medallas de CUALQUIER usuario (Público, para ver perfiles de amigos)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # JOIN para sacar los detalles del logro
        sql = """
            SELECT l.nombre, l.descripcion, l.icono, rl.fecha_obtenido 
            FROM runner_logro rl
            JOIN logro l ON rl.id_logro = l.id_logro
            WHERE rl.id_runner = %s
            ORDER BY rl.fecha_obtenido DESC
        """
        cur.execute(sql, (id_runner,))
        mis_logros = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for l in mis_logros:
            lista.append({
                "titulo": l[0], 
                "descripcion": l[1], 
                "icono": l[2], 
                "fecha": l[3]
            })
            
        return {"id_runner": id_runner, "total_ganados": len(lista), "medallas": lista}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logros/catalogo")
def listar_logros_disponibles():
    """Muestra todas las medallas que existen en el juego"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Seleccionamos las columnas de tu tabla
        cur.execute("SELECT id_logro, nombre, descripcion, icono, categoria, criterio FROM logro")
        logros = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for l in logros:
            lista.append({
                "id": l[0], 
                "titulo": l[1], 
                "descripcion": l[2], 
                "icono": l[3],       
                "categoria": l[4],
                "criterio": l[5]
            })
            
        return {"total_disponibles": len(lista), "catalogo": lista}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))