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
    hexagonos_strings = set()
    
    if len(puntos) < 2:
        if len(puntos) == 1:
            h3_index = h3.latlng_to_cell(puntos[0].latitud, puntos[0].longitud, RESOLUCION_H3)
            hexagonos_strings.add(h3_index)
        return {int(h, 16) for h in hexagonos_strings}

    for i in range(len(puntos) - 1):
        p1 = puntos[i]
        p2 = puntos[i+1]
        h3_inicio = h3.latlng_to_cell(p1.latitud, p1.longitud, RESOLUCION_H3)
        h3_fin = h3.latlng_to_cell(p2.latitud, p2.longitud, RESOLUCION_H3)
        
        try:
            camino = h3.grid_path_cells(h3_inicio, h3_fin)
            hexagonos_strings.update(camino)
        except Exception:
            hexagonos_strings.add(h3_inicio)
            hexagonos_strings.add(h3_fin)
            
    return {int(h, 16) for h in hexagonos_strings}

# --- ENDPOINTS ---

@router.post("/carreras/guardar")
def guardar_carrera(
    carrera: CarreraCreate,
    id_runner_autenticado: int = Depends(obtener_runner_actual)
):
    """Guarda ruta y calcula resultados de batalla detallados"""
    
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
        
        # A. Guardar Ruta
        distancia_metros = carrera.distancia_km * 1000
        sql_ruta = """
            INSERT INTO ruta (id_runner, fecha_hora_inicio, distancia_metros, duracion_segundos) 
            VALUES (%s, NOW(), %s, %s) 
            RETURNING id_ruta;
        """
        cur.execute(sql_ruta, (id_runner_autenticado, distancia_metros, carrera.tiempo_segundos))
        id_ruta = cur.fetchone()[0]
        
        # B. Guardar Track
        start_time = carrera.puntos[0].timestamp if carrera.puntos else datetime.datetime.now()
        sql_puntos = """
            INSERT INTO track_point (id_ruta, latitud, longitud, orden, timestamp_relativo)
            VALUES (%s, %s, %s, %s, %s)
        """
        datos_puntos = []
        for p in carrera.puntos:
            delta_seconds = (p.timestamp - start_time).total_seconds()
            datos_puntos.append((id_ruta, p.latitud, p.longitud, p.orden, delta_seconds))
        cur.executemany(sql_puntos, datos_puntos)
        
        # C. Lógica de Guerra (Actualizada para detectar Robos)
        cur.execute("SELECT id_equipo FROM runner_equipo WHERE id_runner = %s", (id_runner_autenticado,))
        res_equipo = cur.fetchone()
        id_equipo = res_equipo[0] if res_equipo else None
        
        color_zona = "#808080"
        if id_equipo == 1: color_zona = "#FF0000"
        elif id_equipo == 2: color_zona = "#0000FF"
        
        # Contadores para el mensaje final
        zonas_nuevas = 0    # Antes no había nadie
        zonas_robadas = 0   # Antes era de otro
        zonas_defendidas = 0 # Ya era mía
        
        for h3_index_int in ids_hexagonos:
            # 1. Miramos de quién es la zona AHORA MISMO
            cur.execute("SELECT id_runner FROM zona WHERE id_zona = %s", (h3_index_int,))
            res_zona = cur.fetchone()
            
            tipo_accion = "CONQUISTA" # Por defecto
            
            if res_zona is None:
                zonas_nuevas += 1
                tipo_accion = "NUEVA"
            elif res_zona[0] == id_runner_autenticado:
                zonas_defendidas += 1
                tipo_accion = "DEFENSA"
            else:
                zonas_robadas += 1
                tipo_accion = "ROBO"

            # 2. Aplicamos el cambio (UPSERT)
            sql_upsert = """
                INSERT INTO zona (id_zona, id_runner, id_equipo, color_hex, fecha_conquista)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (id_zona) DO UPDATE SET 
                    id_runner = EXCLUDED.id_runner,
                    id_equipo = EXCLUDED.id_equipo,
                    color_hex = EXCLUDED.color_hex,
                    fecha_conquista = NOW();
            """
            cur.execute(sql_upsert, (h3_index_int, id_runner_autenticado, id_equipo, color_zona))
            
            # 3. Guardamos en historial con el tipo correcto
            cur.execute("""
                INSERT INTO captura_zona (id_zona, id_runner, id_ruta, tipo_captura, puntos_ganados)
                VALUES (%s, %s, %s, %s, 10)
            """, (h3_index_int, id_runner_autenticado, id_ruta, tipo_accion))
            
        conn.commit()
        cur.close(); conn.close()
        
        # D. Generar Mensaje Inteligente para Flutter
        mensaje_final = "Carrera finalizada."
        titulo_batalla = "Entrenamiento completado"
        
        if zonas_robadas > 0:
            titulo_batalla = "¡ZONA CONQUISTADA! ⚔️"
            mensaje_final = f"Has robado {zonas_robadas} zonas al enemigo y capturado {zonas_nuevas} nuevas."
        elif zonas_nuevas > 0:
            titulo_batalla = "¡TERRITORIO EXPANDIDO! 🚩"
            mensaje_final = f"Has reclamado {zonas_nuevas} zonas nuevas para tu equipo."
        elif zonas_defendidas > 0:
            titulo_batalla = "DEFENSA EXITOSA 🛡️"
            mensaje_final = f"Has reforzado {zonas_defendidas} de tus zonas."

        return {
            "mensaje": mensaje_final,
            "titulo": titulo_batalla, # Para que Flutter lo ponga en negrita o grande
            "id_ruta": id_ruta, 
            "estadisticas": {
                "nuevas": zonas_nuevas,
                "robadas": zonas_robadas,
                "defendidas": zonas_defendidas,
                "total": len(ids_hexagonos)
            }
        }

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carreras/historial/{id_runner}")
def ver_mis_carreras(id_runner: int):
    # (El código del historial sigue igual, no hace falta cambiarlo)
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