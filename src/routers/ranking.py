from fastapi import APIRouter, HTTPException
from src.database import get_db_connection

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