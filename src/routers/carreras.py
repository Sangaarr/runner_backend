from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual
import datetime
import h3 

router = APIRouter()

# --- CONFIGURACIÓN H3 ---
RESOLUCION_H3 = 10 

# --- MODELOS ---
class PuntoGPS(BaseModel):
    latitud: float
    longitud: float
    orden: int
    timestamp: datetime.datetime

class CarreraCreate(BaseModel):
    distancia_km: float
    tiempo_segundos: int
    ritmo_min_km: float
    puntos: List[PuntoGPS]

# --- LÓGICA DE CÁLCULO DE TERRITORIO (H3) ---
def calcular_hexagonos_conquistados(puntos: List[PuntoGPS]) -> set:
    hexagonos_conquistados = set()
    
    if len(puntos) < 2:
        if len(puntos) == 1:
            h3_index = h3.latlng_to_cell(puntos[0].latitud, puntos[0].longitud, RESOLUCION_H3)
            hexagonos_conquistados.add(h3_index)
        return hexagonos_conquistados

    for i in range(len(puntos) - 1):
        p1 = puntos[i]
        p2 = puntos[i+1]
        h3_inicio = h3.latlng_to_cell(p1.latitud, p1.longitud, RESOLUCION_H3)
        h3_fin = h3.latlng_to_cell(p2.latitud, p2.longitud, RESOLUCION_H3)
        
        try:
            camino = h3.grid_path_cells(h3_inicio, h3_fin)
            hexagonos_conquistados.update(camino)
        except Exception:
            hexagonos_conquistados.add(h3_inicio)
            hexagonos_conquistados.add(h3_fin)
            
    return hexagonos_conquistados

# --- ENDPOINTS ---

@router.post("/carreras/guardar")
def guardar_carrera(
    carrera: CarreraCreate,
    id_runner_autenticado: int = Depends(obtener_runner_actual)
):
    """Guarda ruta y conquista territorio"""
    
    # --- 1. ANTI-CHEAT ---
    if carrera.tiempo_segundos <= 0:
        raise HTTPException(status_code=400, detail="El tiempo no puede ser 0.")

    velocidad_media_kmh = (carrera.distancia_km / carrera.tiempo_segundos) * 3600
    if velocidad_media_kmh > 35.0:
        raise HTTPException(status_code=400, detail="Velocidad sospechosa.")
    
    # --- 2. CÁLCULO H3 ---
    ids_hexagonos = calcular_hexagonos_conquistados(carrera.puntos)

    # --- 3. BASE DE DATOS ---
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # A. Guardar la Ruta
        distancia_metros = carrera.distancia_km * 1000
        
        sql_ruta = """
            INSERT INTO ruta (id_runner, fecha_hora_inicio, distancia_metros, duracion_segundos) 
            VALUES (%s, NOW(), %s, %s) 
            RETURNING id_ruta;
        """
        cur.execute(sql_ruta, (id_runner_autenticado, distancia_metros, carrera.tiempo_segundos))
        id_ruta = cur.fetchone()[0]
        
        # B. Guardar Puntos GPS (CORREGIDO PARA TU TABLA)
        # Calculamos el tiempo relativo (segundos desde el primer punto)
        start_time = carrera.puntos[0].timestamp if carrera.puntos else datetime.datetime.now()
        
        sql_puntos = """
            INSERT INTO track_point (id_ruta, latitud, longitud, orden, timestamp_relativo)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        datos_puntos = []
        for p in carrera.puntos:
            # Calculamos diferencia en segundos
            delta_seconds = (p.timestamp - start_time).total_seconds()
            datos_puntos.append((id_ruta, p.latitud, p.longitud, p.orden, delta_seconds))
            
        cur.executemany(sql_puntos, datos_puntos)
        
        # C. Actualizar Mapa
        cur.execute("SELECT id_equipo FROM runner_equipo WHERE id_runner = %s", (id_runner_autenticado,))
        res_equipo = cur.fetchone()
        id_equipo = res_equipo[0] if res_equipo else None
        
        color_zona = "#808080"
        if id_equipo == 1: color_zona = "#FF0000"
        elif id_equipo == 2: color_zona = "#0000FF"
        
        conquistas_nuevas = 0
        
        for h3_index in ids_hexagonos:
            sql_upsert = """
                INSERT INTO zona (id_zona, id_runner, id_equipo, color_hex, fecha_conquista)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (id_zona) DO UPDATE SET 
                    id_runner = EXCLUDED.id_runner,
                    id_equipo = EXCLUDED.id_equipo,
                    color_hex = EXCLUDED.color_hex,
                    fecha_conquista = NOW();
            """
            cur.execute(sql_upsert, (h3_index, id_runner_autenticado, id_equipo, color_zona))
            
            cur.execute("""
                INSERT INTO captura_zona (id_zona, id_runner, id_ruta, tipo_captura, puntos_ganados)
                VALUES (%s, %s, %s, 'NORMAL', 10)
            """, (h3_index, id_runner_autenticado, id_ruta))
            
            conquistas_nuevas += 1
        
        conn.commit()
        cur.close(); conn.close()
        
        return {
            "mensaje": "Carrera guardada 🏁", 
            "id_ruta": id_ruta, 
            "zonas_conquistadas": conquistas_nuevas
        }

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carreras/historial/{id_runner}")
def ver_mis_carreras(id_runner: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT id_ruta, fecha_hora_inicio, distancia_metros, duracion_segundos 
            FROM ruta 
            WHERE id_runner = %s 
            ORDER BY fecha_hora_inicio DESC
        """
        cur.execute(sql, (id_runner,))
        filas = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for f in filas:
            dist_km = f[2] / 1000 if f[2] else 0
            lista.append({
                "id_ruta": f[0],
                "fecha": f[1],
                "distancia": f"{dist_km:.2f} km",
                "duracion": f"{f[3]} seg"
            })
            
        return {"historial": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))