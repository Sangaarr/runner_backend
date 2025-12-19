from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.database import get_db_connection
import datetime

router = APIRouter()

# --- MODELOS ---
class EquipoCreate(BaseModel):
    nombre: str
    descripcion: str
    ciudad_base: str

class UnirseEquipoRequest(BaseModel):
    id_runner: int
    id_equipo: int

class SeguirRequest(BaseModel):
    id_seguidor: int
    id_seguido: int

# --- ENDPOINTS EQUIPOS ---
@router.post("/equipos")
def crear_equipo(equipo: EquipoCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = "INSERT INTO equipo (nombre, descripcion, ciudad_base) VALUES (%s, %s, %s) RETURNING id_equipo;"
        cur.execute(sql, (equipo.nombre, equipo.descripcion, equipo.ciudad_base))
        id_equipo = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "¡Equipo Fundado! 🛡️", "id_equipo": id_equipo, "nombre": equipo.nombre}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/equipos/unirse")
def unirse_equipo(datos: UnirseEquipoRequest):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = "INSERT INTO runner_equipo (id_runner, id_equipo, rol, fecha_union) VALUES (%s, %s, 'Miembro', NOW()) RETURNING fecha_union;"
        cur.execute(sql, (datos.id_runner, datos.id_equipo))
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "¡Te has unido al equipo! 🤝", "equipo_id": datos.id_equipo}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error al unirse: {str(e)}")

@router.get("/equipos/{id_equipo}/miembros")
def ver_miembros_equipo(id_equipo: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, re.rol, re.fecha_union FROM runner_equipo re
            JOIN runner r ON re.id_runner = r.id_runner WHERE re.id_equipo = %s;
        """
        cur.execute(sql, (id_equipo,))
        miembros = cur.fetchall()
        cur.close(); conn.close()
        lista = [{"usuario": m[0], "rol": m[1], "desde": m[2]} for m in miembros]
        return {"id_equipo": id_equipo, "total_miembros": len(lista), "miembros": lista}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS SOCIALES ---
@router.post("/social/seguir")
def seguir_usuario(datos: SeguirRequest):
    if datos.id_seguidor == datos.id_seguido: raise HTTPException(status_code=400, detail="No puedes seguirte a ti mismo")
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO seguidor (id_seguidor, id_seguido, fecha_desde) VALUES (%s, %s, NOW())", (datos.id_seguidor, datos.id_seguido))
        cur.execute("INSERT INTO notificacion (id_runner, tipo, titulo, mensaje, leida, fecha_hora) VALUES (%s, 'SOCIAL', 'Nuevo Seguidor', '¡Alguien te sigue!', FALSE, NOW())", (datos.id_seguido,))
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "¡Ahora sigues a este usuario! 👀"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/social/feed/{id_mi_usuario}")
def obtener_feed_amigos(id_mi_usuario: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, z.municipio, cz.puntos_ganados, cz.fecha_hora, cz.tipo_captura
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE cz.id_runner IN (SELECT id_seguido FROM seguidor WHERE id_seguidor = %s)
            ORDER BY cz.fecha_hora DESC LIMIT 20;
        """
        cur.execute(sql, (id_mi_usuario,))
        feed = [{"usuario": i[0], "accion": f"Conquistó una zona en {i[1]}", "puntos": i[2], "cuando": i[3]} for i in cur.fetchall()]
        cur.close(); conn.close()
        return {"feed": feed}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notificaciones/{id_usuario}")
def ver_notificaciones(id_usuario: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        cur.execute("SELECT tipo, titulo, mensaje, fecha_hora, leida FROM notificacion WHERE id_runner = %s ORDER BY fecha_hora DESC", (id_usuario,))
        notis = [{"tipo":n[0], "titulo":n[1], "mensaje":n[2], "fecha":n[3], "nueva":not n[4]} for n in cur.fetchall()]
        cur.execute("UPDATE notificacion SET leida = TRUE WHERE id_runner = %s", (id_usuario,))
        conn.commit()
        cur.close(); conn.close()
        return {"tus_notificaciones": notis}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))