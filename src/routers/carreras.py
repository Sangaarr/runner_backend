from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual
import datetime
import h3  # 👈 IMPORTANTE: Asegúrate de tener 'pip install h3'

router = APIRouter()

# --- CONFIGURACIÓN H3 ---
# Resolución 10: Hexágonos de ~66m de lado (Tamaño calle/edificio)
RESOLUCION_H3 = 10  

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

# --- LÓGICA DE CÁLCULO DE TERRITORIO (H3) ---
def calcular_hexagonos_conquistados(puntos: List[PuntoGPS]) -> set:
    """
    Toma la lista de puntos GPS y devuelve un SET de IDs de hexágonos H3 únicos.
    Usa interpolación para unir los puntos y pintar el camino completo.
    """
    hexagonos_conquistados = set()
    
    # Si hay muy pocos puntos, solo calculamos dónde está parado
    if len(puntos) < 2:
        if len(puntos) == 1:
            h3_index = h3.latlng_to_cell(puntos[0].latitud, puntos[0].longitud, RESOLUCION_H3)
            hexagonos_conquistados.add(h3_index)
        return hexagonos_conquistados

    # Unimos los puntos paso a paso
    for i in range(len(puntos) - 1):
        p1 = puntos[i]
        p2 = puntos[i+1]
        
        # Obtenemos hexágonos de inicio y fin
        h3_inicio = h3.latlng_to_cell(p1.latitud, p1.longitud, RESOLUCION_H3)
        h3_fin = h3.latlng_to_cell(p2.latitud, p2.longitud, RESOLUCION_H3)
        
        try:
            # H3 rellena el camino entre los dos puntos
            camino = h3.grid_path_cells(h3_inicio, h3_fin)
            hexagonos_conquistados.update(camino)
        except Exception:
            # Si falla (puntos muy lejanos), guardamos al menos los extremos
            hexagonos_conquistados.add(h3_inicio)
            hexagonos_conquistados.add(h3_fin)
            
    return hexagonos_conquistados

# --- ENDPOINTS ---

@router.post("/carreras/guardar")
def guardar_carrera(
    carrera: CarreraCreate,
    id_runner_autenticado: int = Depends(obtener_runner_actual)
):
    """Guarda ruta, puntos GPS y ACTUALIZA EL MAPA DE CONQUISTA"""
    
    # --- 🚨 1. BLOQUE ANTI-CHEAT (INTACTO) 🚨 ---
    if carrera.tiempo_segundos <= 0:
        raise HTTPException(status_code=400, detail="El tiempo de carrera no puede ser 0.")

    velocidad_media_kmh = (carrera.distancia_km / carrera.tiempo_segundos) * 3600
    LIMITE_VELOCIDAD = 35.0 # Subido un poco por seguridad, pero puedes dejarlo en 30
    
    if velocidad_media_kmh > LIMITE_VELOCIDAD:
        print(f"⚠️ ALERTA CHEATER: Usuario {id_runner_autenticado} intentó subir carrera a {velocidad_media_kmh:.2f} km/h")
        raise HTTPException(
            status_code=400, 
            detail=f"Carrera rechazada: Velocidad media ({velocidad_media_kmh:.1f} km/h) sospechosa de vehículo."
        )
    
    # --- 2. CÁLCULO DE HEXÁGONOS (NUEVO) ---
    ids_hexagonos = calcular_hexagonos_conquistados(carrera.puntos)
    print(f"DEBUG: Carrera válida. Conquistando {len(ids_hexagonos)} hexágonos.")

    # --- 3. BASE DE DATOS ---
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # A. Guardar la Cabecera (INTACTO)
        sql_ruta = """
            INSERT INTO ruta (id_runner, fecha_inicio, distancia_km, tiempo_total) 
            VALUES (%s, NOW(), %s, %s) 
            RETURNING id_ruta;
        """
        cur.execute(sql_ruta, (id_runner_autenticado, carrera.distancia_km, carrera.tiempo_segundos))
        id_ruta = cur.fetchone()[0]
        
        # B. Guardar los Puntos GPS (INTACTO)
        sql_puntos = """
            INSERT INTO track_point (id_ruta, latitud, longitud, orden, fecha_hora)
            VALUES (%s, %s, %s, %s, %s)
        """
        datos_puntos = [
            (id_ruta, p.latitud, p.longitud, p.orden, p.timestamp) 
            for p in carrera.puntos
        ]
        cur.executemany(sql_puntos, datos_puntos)
        
        # C. --- ACTUALIZAR ZONAS Y CONQUISTA (NUEVO) ---
        
        # 1. Buscamos el equipo del usuario (para saber de qué color pintar)
        # Si no tiene equipo, asignamos NULL o un color gris por defecto
        cur.execute("SELECT id_equipo FROM runner_equipo WHERE id_runner = %s", (id_runner_autenticado,))
        res_equipo = cur.fetchone()
        id_equipo = res_equipo[0] if res_equipo else None
        
        # Lógica de colores simple (puedes mejorarla luego leyendo de la tabla equipo)
        color_zona = "#808080" # Gris por defecto
        if id_equipo == 1: color_zona = "#FF0000" # Rojo
        elif id_equipo == 2: color_zona = "#0000FF" # Azul
        
        conquistas_nuevas = 0
        
        # 2. Bucle para actualizar cada hexágono pisado
        for h3_index_int in ids_hexagonos:
            # Upsert: Si existe actualiza, si no crea
            sql_upsert_zona = """
                INSERT INTO zona (id_zona, id_runner, id_equipo, color_hex, fecha_conquista)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (id_zona) 
                DO UPDATE SET 
                    id_runner = EXCLUDED.id_runner,
                    id_equipo = EXCLUDED.id_equipo,
                    color_hex = EXCLUDED.color_hex,
                    fecha_conquista = NOW();
            """
            cur.execute(sql_upsert_zona, (h3_index_int, id_runner_autenticado, id_equipo, color_zona))
            
            # Guardar en historial
            cur.execute("""
                INSERT INTO captura_zona (id_zona, id_runner, id_ruta, tipo_captura, puntos_ganados)
                VALUES (%s, %s, %s, 'NORMAL', 10)
            """, (h3_index_int, id_runner_autenticado, id_ruta))
            
            conquistas_nuevas += 1
        
        conn.commit()
        cur.close(); conn.close()
        
        return {
            "mensaje": "Carrera guardada con éxito 🏁", 
            "id_ruta": id_ruta, 
            "velocidad_registrada": f"{velocidad_media_kmh:.1f} km/h",
            "zonas_conquistadas": conquistas_nuevas
        }

    except Exception as e:
        if conn: conn.rollback()
        print(f"ERROR: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carreras/historial/{id_runner}")
def ver_mis_carreras(id_runner: int):
    # --- ENDPOINT ORIGINAL INTACTO ---
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