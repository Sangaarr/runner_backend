from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.database import get_db_connection
import datetime

router = APIRouter()

class TemporadaCreate(BaseModel):
    nombre: str
    fecha_inicio: datetime.datetime
    fecha_fin: datetime.datetime

@router.get("/temporadas/actual")
def obtener_temporada_actual():
    """Devuelve la temporada activa. Si no hay, crea una automática para el mes actual."""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        ahora = datetime.datetime.now()
        
        # 1. Buscamos si hay una temporada activa hoy
        sql = "SELECT id_temporada, nombre, fecha_inicio, fecha_fin FROM temporada WHERE %s BETWEEN fecha_inicio AND fecha_fin LIMIT 1"
        cur.execute(sql, (ahora,))
        res = cur.fetchone()
        
        if res:
            cur.close(); conn.close()
            return {"id": res[0], "nombre": res[1], "inicio": res[2], "fin": res[3]}
        
        # 2. Si NO hay temporada (ej: es el día 1 del mes), ¡CREAMOS UNA!
        # La llamaremos "Temporada [Mes] [Año]"
        nombre_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        nombre_nueva = f"Temporada {nombre_meses[ahora.month]} {ahora.year}"
        
        # Definimos inicio (hoy) y fin (dentro de 30 días aprox, o fin de mes)
        # Para simplificar, la haremos de 30 días desde hoy
        inicio = now = datetime.datetime.now()
        fin = inicio + datetime.timedelta(days=30)
        
        sql_crear = "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin) VALUES (%s, %s, %s) RETURNING id_temporada"
        cur.execute(sql_crear, (nombre_nueva, inicio, fin))
        nuevo_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close(); conn.close()
        return {"mensaje": "Nueva temporada inaugurada automáticamente", "id": nuevo_id, "nombre": nombre_nueva}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))