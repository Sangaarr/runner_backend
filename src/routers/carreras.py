from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual
import datetime

router = APIRouter()

# --- MODELOS ---
class PuntoGPS(BaseModel):
    latitud: float
    longitud: float
    orden: int
    timestamp: datetime.datetime

class CarreraCreate(BaseModel):
    # id_runner eliminado (viene del token)
    distancia_km: float
    tiempo_segundos: int
    ritmo_min_km: float
    puntos: List[PuntoGPS]

# --- ENDPOINT ---
@router.post("/carreras/guardar")
def guardar_carrera(
    carrera: CarreraCreate,
    id_runner_autenticado: int = Depends(obtener_runner_actual)
):
    """Guarda una ruta finalizada y sus puntos GPS (Con Anti-Cheat básico)"""
    
    # --- 🚨 BLOQUE ANTI-CHEAT 🚨 ---
    
    # 1. Evitar división por cero
    if carrera.tiempo_segundos <= 0:
        raise HTTPException(status_code=400, detail="El tiempo de carrera no puede ser 0.")

    # 2. Calcular velocidad media en km/h
    # (Distancia km / Tiempo segundos) * 3600 segundos/hora
    velocidad_media_kmh = (carrera.distancia_km / carrera.tiempo_segundos) * 3600
    
    # 3. Límite Humano (30 km/h es muy generoso, el récord de maratón es ~21 km/h)
    LIMITE_VELOCIDAD = 30.0 
    
    if velocidad_media_kmh > LIMITE_VELOCIDAD:
        print(f"⚠️ ALERTA CHEATER: Usuario {id_runner_autenticado} intentó subir carrera a {velocidad_media_kmh:.2f} km/h")
        raise HTTPException(
            status_code=400, 
            detail=f"Carrera rechazada: Velocidad media ({velocidad_media_kmh:.1f} km/h) sospechosa de vehículo."
        )
    
    # ---------------------------------

    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Guardar la Cabecera
        sql_ruta = """
            INSERT INTO ruta (id_runner, fecha_inicio, distancia_km, tiempo_total) 
            VALUES (%s, NOW(), %s, %s) 
            RETURNING id_ruta;
        """
        cur.execute(sql_ruta, (id_runner_autenticado, carrera.distancia_km, carrera.tiempo_segundos))
        id_ruta = cur.fetchone()[0]
        
        # 2. Guardar los Puntos
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
        
        return {"mensaje": "Carrera guardada con éxito 🏁", "id_ruta": id_ruta, "velocidad_registrada": f"{velocidad_media_kmh:.1f} km/h"}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carreras/historial/{id_runner}")
def ver_mis_carreras(id_runner: int):
    # Endpoint público para ver perfiles (sin cambios)
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
                "duracion": f"{f[3]} seg"
            })
            
        return {"historial": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))