from fastapi import APIRouter, HTTPException
from src.database import get_db_connection
import datetime 

router = APIRouter()

# --- 1. RANKING GLOBAL ---
@router.get("/ranking/global")
def ranking_global():
    """Top 10 jugadores con más puntos en todo el juego"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql)
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        # Formateamos la respuesta como le gusta a tu Front
        return {
            "titulo": "🏆 TOP MUNDIAL", 
            "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]
        }
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. RANKING POR PAÍS ---
@router.get("/ranking/pais/{pais}")
def ranking_pais(pais: str):
    """Top 10 jugadores con más puntos en un país concreto (ej: España)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # JOIN con ZONA para filtrar por país
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE z.pais = %s
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql, (pais,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {
            "titulo": f"🇪🇸 TOP {pais.upper()}", 
            "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]
        }
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. RANKING POR CIUDAD ---
@router.get("/ranking/ciudad/{municipio}")
def ranking_ciudad(municipio: str):
    """Top 10 jugadores en una ciudad concreta (ej: Madrid)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # JOIN con ZONA para filtrar por municipio
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE z.municipio = %s
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql, (municipio,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {
            "titulo": f"🏙️ TOP {municipio.upper()}", 
            "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]
        }
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))


# --- RANKING POR TEMPORADA ---
@router.get("/ranking/temporada")
def ranking_temporada_actual():
    """Top jugadores SOLO contando los puntos de la temporada actual"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Sacamos las fechas de la temporada actual
        ahora = datetime.datetime.now()
        cur.execute("SELECT fecha_inicio, fecha_fin FROM temporada WHERE %s BETWEEN fecha_inicio AND fecha_fin LIMIT 1", (ahora,))
        temp = cur.fetchone()
        
        if not temp:
            return {"mensaje": "No hay temporada activa, no hay ranking estacional."}
            
        inicio, fin = temp
        
        # 2. Calculamos puntos filtrando por fecha
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            WHERE cz.fecha_hora BETWEEN %s AND %s
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql, (inicio, fin))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {
            "titulo": "📅 RANKING DE TEMPORADA", 
            "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# --- RANKING DE EQUIPOS ---
@router.get("/ranking/equipos")
def ranking_equipos():
    """Top Equipos (Suma de los puntos de todos sus miembros)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # JOIN Múltiple: Equipo -> Miembros -> Capturas
        sql = """
            SELECT e.nombre, SUM(cz.puntos_ganados) as total_equipo
            FROM equipo e
            JOIN runner_equipo re ON e.id_equipo = re.id_equipo
            JOIN captura_zona cz ON re.id_runner = cz.id_runner
            GROUP BY e.nombre
            ORDER BY total_equipo DESC
            LIMIT 10;
        """
        cur.execute(sql)
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for i, r in enumerate(resultados):
            pts = r[1] if r[1] else 0 # Si el equipo no tiene puntos, poner 0
            lista.append({"pos": i+1, "equipo": r[0], "pts": pts})
            
        return {"titulo": "🛡️ MEJORES CLANES", "ranking": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/ranking/equipos/temporada")
def ranking_equipos_temporada():
    """Top Equipos SOLO sumando los puntos conseguidos en la TEMPORADA ACTUAL"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Sacamos fechas de la temporada actual
        ahora = datetime.datetime.now()
        cur.execute("SELECT fecha_inicio, fecha_fin, nombre FROM temporada WHERE %s BETWEEN fecha_inicio AND fecha_fin LIMIT 1", (ahora,))
        temp = cur.fetchone()
        
        if not temp:
            return {"mensaje": "No hay temporada activa, no hay ranking de equipos estacional."}
            
        inicio, fin, nombre_temp = temp
        
        # 2. SQL Mágico: Equipos + Miembros + Capturas (Filtradas por fecha)
        sql = """
            SELECT e.nombre, SUM(cz.puntos_ganados) as total_equipo
            FROM equipo e
            JOIN runner_equipo re ON e.id_equipo = re.id_equipo
            JOIN captura_zona cz ON re.id_runner = cz.id_runner
            WHERE cz.fecha_hora BETWEEN %s AND %s  -- <--- AQUÍ ESTÁ LA CLAVE
            GROUP BY e.nombre
            ORDER BY total_equipo DESC
            LIMIT 10;
        """
        cur.execute(sql, (inicio, fin))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for i, r in enumerate(resultados):
            pts = r[1] if r[1] else 0
            lista.append({"pos": i+1, "equipo": r[0], "pts": pts})
            
        return {
            "titulo": f"🛡️ CLANES LÍDERES - {nombre_temp.upper()}", 
            "ranking": lista
        }
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))