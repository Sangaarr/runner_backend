from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import get_db_connection
import datetime

app = FastAPI(
    title="RunnerApp API",
    description="Backend para BattleRun Mobile - Versión Grid",
    version="1.2.0"
)

# --- MODELOS DE DATOS (PYDANTIC) ---
# Definimos qué datos esperamos recibir del móvil

class RunnerCreate(BaseModel):
    email: str
    password: str
    username: str

# Modelo adaptado a tu tabla 'zona' real
class ZonaCreate(BaseModel):
    sistema_grid: str       # Ej: "MGRS"
    codigo_celda: str       # Ej: "30TVK"
    geometria: str          # Ej: "POLYGON(...)"
    pais: str
    provincia: str
    municipio: str

# Modelo adaptado a tu tabla 'captura_zona' real
class CapturaCreate(BaseModel):
    id_runner: int
    id_zona: int
    tipo_captura: str = "NORMAL"   # Valor por defecto
    puntos_ganados: int = 10       # Valor por defecto

# --- RUTAS DE USUARIOS (RUNNERS) ---

@app.get("/")
def raiz():
    return {"mensaje": "Servidor BattleRun Operativo 🌍🏃"}

@app.get("/runners")
def obtener_runners():
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_runner, username, email, estado_cuenta FROM runner;")
        filas = cur.fetchall()
        resultado = [{"id": f[0], "usuario": f[1], "email": f[2], "estado": f[3]} for f in filas]
        cur.close()
        conn.close()
        return resultado
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/runners")
def crear_runner(nuevo_usuario: RunnerCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO runner (email, password_hash, username, estado_cuenta)
            VALUES (%s, %s, %s, 'ACTIVA')
            RETURNING id_runner;
        """
        cur.execute(sql, (nuevo_usuario.email, nuevo_usuario.password, nuevo_usuario.username))
        id_gen = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"mensaje": "Runner creado", "id": id_gen, "usuario": nuevo_usuario.username}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error creando runner: {str(e)}")

# --- RUTAS DE JUEGO (ZONAS Y CAPTURAS) ---

@app.post("/zonas")
def crear_zona(nueva_zona: ZonaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Insertamos en las columnas que vi en tu foto de DBeaver
        sql = """
            INSERT INTO zona (sistema_grid, codigo_celda, geometria, pais, provincia, municipio)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_zona;
        """
        datos = (
            nueva_zona.sistema_grid, 
            nueva_zona.codigo_celda, 
            nueva_zona.geometria,
            nueva_zona.pais,
            nueva_zona.provincia,
            nueva_zona.municipio
        )
        
        cur.execute(sql, datos)
        id_zona = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"mensaje": "Zona registrada en el Grid 📍", "id_zona": id_zona, "celda": nueva_zona.codigo_celda}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error creando zona: {str(e)}")

@app.post("/capturas")
def registrar_captura(datos: CapturaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # Usamos la tabla 'captura_zona' que vi en tu otra foto
        # Dejamos id_ruta como NULL porque aún no tenemos rutas
        sql = """
            INSERT INTO captura_zona (id_runner, id_zona, fecha_hora, tipo_captura, puntos_ganados)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_captura;
        """
        
        ahora = datetime.datetime.now()
        
        cur.execute(sql, (
            datos.id_runner, 
            datos.id_zona, 
            ahora, 
            datos.tipo_captura, 
            datos.puntos_ganados
        ))
        
        id_captura = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "mensaje": "¡TERRITORIO CONQUISTADO! 🚩",
            "id_captura": id_captura,
            "puntos": datos.puntos_ganados,
            "fecha": ahora
        }
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error al capturar: {str(e)}")