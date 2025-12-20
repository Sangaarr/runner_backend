from fastapi import APIRouter, HTTPException, Depends # <--- Importamos Depends
from pydantic import BaseModel
from src.database import get_db_connection
from src.dependencies import obtener_runner_actual # <--- Importamos seguridad

router = APIRouter()

class ZonaCreate(BaseModel):
    sistema_grid: str
    codigo_celda: str
    geometria: str
    pais: str
    provincia: str
    municipio: str

# --- PROTEGEMOS LA CREACIÓN DE ZONAS ---
@router.post("/zonas")
def crear_zona(
    nueva_zona: ZonaCreate,
    # Al pedir el token, nos aseguramos de que al menos es un usuario registrado.
    # (En el futuro, aquí verificaríamos si id_runner_autenticado es ADMIN)
    id_runner_autenticado: int = Depends(obtener_runner_actual) 
):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = "INSERT INTO zona (sistema_grid, codigo_celda, geometria, pais, provincia, municipio) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_zona;"
        cur.execute(sql, (nueva_zona.sistema_grid, nueva_zona.codigo_celda, nueva_zona.geometria, nueva_zona.pais, nueva_zona.provincia, nueva_zona.municipio))
        id_gen = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "Zona registrada", "id_zona": id_gen}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# --- LOS GET LOS DEJAMOS PÚBLICOS ---
@router.get("/zonas/mapa/estado")
def obtener_estado_mapa():
    conn = get_db_connection()
    # ... (El resto del código de lectura se queda igual, sin Depends) ...
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            SELECT DISTINCT ON (z.id_zona) z.id_zona, z.municipio, r.username, cz.fecha_hora
            FROM zona z
            LEFT JOIN captura_zona cz ON z.id_zona = cz.id_zona
            LEFT JOIN runner r ON cz.id_runner = r.id_runner
            ORDER BY z.id_zona, cz.fecha_hora DESC;
        """
        cur.execute(sql)
        zonas = cur.fetchall()
        cur.close(); conn.close()
        
        lista_mapa = []
        for z in zonas:
            dueno = z[2] if z[2] else "ZONA NEUTRAL"
            lista_mapa.append({"id_zona": z[0], "municipio": z[1], "propietario": dueno, "conquistada_el": z[3]})
        return {"total_zonas": len(lista_mapa), "mapa": lista_mapa}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zonas/{id_zona}/info")
def info_zona_detalle(id_zona: int):
    conn = get_db_connection()
    # ... (Este también público) ...
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, cz.fecha_hora FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            WHERE cz.id_zona = %s ORDER BY cz.fecha_hora DESC LIMIT 1;
        """
        cur.execute(sql, (id_zona,))
        resultado = cur.fetchone()
        cur.close(); conn.close()
        if resultado:
            return {"estado": "OCUPADA", "propietario": resultado[0], "fecha": resultado[1]}
        else:
            return {"estado": "LIBRE", "mensaje": "Esta zona es neutral. ¡Corre a por ella!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))