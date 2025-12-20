from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual # <--- IMPORT SEGURIDAD

router = APIRouter()

# --- MODELO ADAPTADO ---
class PreferenciasUpdate(BaseModel):
    # id_runner: int <--- ELIMINADO
    perfil_publico: bool
    rutas_publicas: bool
    mostrar_en_rankings: bool
    acepta_solicitudes_seguidor: bool
    mostrar_ubicacion: bool
    recibir_notificaciones: bool

# --- ENDPOINTS ---

@router.get("/usuario/preferencias/{id_runner}")
def obtener_preferencias(id_runner: int):
    # Este lo dejamos público (o semi-público) para saber si podemos ver su perfil
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT perfil_publico, rutas_publicas, mostrar_en_rankings, 
                   acepta_solicitudes_seguidor, mostrar_ubicacion, recibir_notificaciones 
            FROM preferencia_privacidad WHERE id_runner = %s
        """
        cur.execute(sql, (id_runner,))
        res = cur.fetchone()
        cur.close(); conn.close()
        
        if res:
            return {
                "perfil_publico": res[0], "rutas_publicas": res[1],
                "mostrar_en_rankings": res[2], "acepta_solicitudes_seguidor": res[3],
                "mostrar_ubicacion": res[4], "recibir_notificaciones": res[5]
            }
        else:
            return {
                "perfil_publico": True, "rutas_publicas": True, "mostrar_en_rankings": True,
                "acepta_solicitudes_seguidor": True, "mostrar_ubicacion": True, "recibir_notificaciones": True
            }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/usuario/preferencias")
def guardar_preferencias(
    datos: PreferenciasUpdate,
    id_runner_autenticado: int = Depends(obtener_runner_actual) # <--- CANDADO
):
    """Guarda o Actualiza TODAS las preferencias del usuario LOGUEADO."""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO preferencia_privacidad (
                id_runner, perfil_publico, rutas_publicas, mostrar_en_rankings, 
                acepta_solicitudes_seguidor, mostrar_ubicacion, recibir_notificaciones
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_runner) DO UPDATE SET
                perfil_publico = EXCLUDED.perfil_publico,
                rutas_publicas = EXCLUDED.rutas_publicas,
                mostrar_en_rankings = EXCLUDED.mostrar_en_rankings,
                acepta_solicitudes_seguidor = EXCLUDED.acepta_solicitudes_seguidor,
                mostrar_ubicacion = EXCLUDED.mostrar_ubicacion,
                recibir_notificaciones = EXCLUDED.recibir_notificaciones;
        """
        # Usamos id_runner_autenticado como primer parámetro
        params = (id_runner_autenticado, datos.perfil_publico, datos.rutas_publicas, datos.mostrar_en_rankings, 
                  datos.acepta_solicitudes_seguidor, datos.mostrar_ubicacion, datos.recibir_notificaciones)
        cur.execute(sql, params)
        
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "Preferencias guardadas correctamente ✅"}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))