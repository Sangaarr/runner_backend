from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.database import get_db_connection
from src.routers import logros
from src.dependencies import obtener_runner_actual
import datetime

router = APIRouter()

class CapturaCreate(BaseModel):
    # id_runner: int  <--- ¡YA NO LO PEDIMOS EN EL JSON! (Seguridad)
    id_zona: int
    tipo_captura: str = "NORMAL"
    puntos_ganados: int = 10

@router.post("/capturas")
def registrar_captura(
    datos: CapturaCreate, 
    id_runner_autenticado: int = Depends(obtener_runner_actual) # <--- AQUÍ OBTENEMOS EL ID DEL TOKEN
):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Investigar dueño anterior
        sql_investigacion = """
            SELECT r.username FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            WHERE cz.id_zona = %s ORDER BY cz.fecha_hora DESC LIMIT 1;
        """
        cur.execute(sql_investigacion, (datos.id_zona,))
        resultado_anterior = cur.fetchone()
        nombre_anterior_dueno = resultado_anterior[0] if resultado_anterior else None
            
        # 2. Registrar captura
        # ⚠️ IMPORTANTE: Usamos 'id_runner_autenticado' en lugar de 'datos.id_runner'
        sql_insertar = """
            INSERT INTO captura_zona (id_runner, id_zona, fecha_hora, tipo_captura, puntos_ganados)
            VALUES (%s, %s, %s, %s, %s) RETURNING id_captura;
        """
        ahora = datetime.datetime.now()
        cur.execute(sql_insertar, (id_runner_autenticado, datos.id_zona, ahora, datos.tipo_captura, datos.puntos_ganados))
        id_captura = cur.fetchone()[0]
        
        conn.commit()
        
        # 3. Verificar Logros
        # ⚠️ IMPORTANTE: También aquí pasamos el ID autenticado
        hubo_premio = logros.verificar_y_otorgar_logros(id_runner_autenticado, conn)
        
        cur.close(); conn.close()
        
        # 4. Mensaje
        if nombre_anterior_dueno:
            if nombre_anterior_dueno == "Tú mismo (Front lo chequeará)":
                mensaje = "Has reforzado tu dominio sobre esta zona."
            else:
                mensaje = f"¡ATAQUE EXITOSO! ⚔️ Has arrebatado esta zona a {nombre_anterior_dueno}."
        else:
            mensaje = "¡NUEVO TERRITORIO! 🚩 Has reclamado una zona neutral."

        if hubo_premio:
            mensaje += " ¡Y has desbloqueado un NUEVO LOGRO! 🏅"
            
        return {"mensaje": mensaje, "puntos_ganados": datos.puntos_ganados, "id_captura": id_captura}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))