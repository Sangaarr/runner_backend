from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from src.database import get_db_connection
import datetime

router = APIRouter()

# --- MODELOS ---
class PuntoGPS(BaseModel):
    latitud: float
    longitud: float
    orden: int
    timestamp: datetime.datetime

class CarreraCreate(BaseModel):
    id_runner: int
    distancia_km: float
    tiempo_segundos: int  # Duración total
    ritmo_min_km: float   # Ritmo medio
    puntos: List[PuntoGPS] # Array con todas las coordenadas

# --- ENDPOINT ---
@router.post("/carreras/guardar")
def guardar_carrera(carrera: CarreraCreate):
    """Guarda una ruta finalizada y sus puntos GPS"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Guardar la Cabecera (Tabla 'ruta')
        # Asumo que tu tabla se llama 'ruta' viendo tus fotos anteriores
        sql_ruta = """
            INSERT INTO ruta (id_runner, fecha_inicio, distancia_km, tiempo_total) 
            VALUES (%s, NOW(), %s, %s) 
            RETURNING id_ruta;
        """
        # Nota: tiempo_total lo guardamos tal cual, o lo convertimos a intervalo según tu DB. 
        # Si tu DB usa INT para segundos, perfecto. Si usa INTERVAL, avísame.
        # Aquí asumo que guardas algo simple o texto/int.
        
        cur.execute(sql_ruta, (carrera.id_runner, carrera.distancia_km, carrera.tiempo_segundos))
        id_ruta = cur.fetchone()[0]
        
        # 2. Guardar los Puntos (Tabla 'track_point')
        # Hacemos un bucle (o un executemany para ser más pro y rápido)
        sql_puntos = """
            INSERT INTO track_point (id_ruta, latitud, longitud, orden, fecha_hora)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        datos_puntos = [
            (id_ruta, p.latitud, p.longitud, p.orden, p.timestamp) 
            for p in carrera.puntos
        ]
        
        cur.executemany(sql_puntos, datos_puntos)
        
        conn.commit()
        cur.close(); conn.close()
        
        return {"mensaje": "Carrera guardada con éxito 🏁", "id_ruta": id_ruta}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carreras/historial/{id_runner}")
def ver_mis_carreras(id_runner: int):
    """Lista las carreras pasadas del usuario"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT id_ruta, fecha_inicio, distancia_km, tiempo_total 
            FROM ruta 
            WHERE id_runner = %s 
            ORDER BY fecha_inicio DESC
        """
        cur.execute(sql, (id_runner,))
        filas = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for f in filas:
            lista.append({
                "id_ruta": f[0],
                "fecha": f[1],
                "distancia": f"{f[2]} km",
                "duracion": f"{f[3]} seg" # El front lo formateará bonito (ej: 25:00)
            })
            
        return {"historial": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))