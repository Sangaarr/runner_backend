from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from database import get_db_connection
import bcrypt
import datetime

app = FastAPI(
    title="RunnerApp API",
    description="Backend BattleRun - Lógica de Juego Activa ⚔️",
    version="2.2.0"
)

# --- SEGURIDAD ---
def encriptar_password(password: str):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def verificar_password(password_plana, password_encriptada):
    return bcrypt.checkpw(password_plana.encode('utf-8'), password_encriptada.encode('utf-8'))

# --- MODELOS ---
class RunnerCreate(BaseModel):
    email: str
    password: str
    username: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ZonaCreate(BaseModel):
    sistema_grid: str
    codigo_celda: str
    geometria: str
    pais: str
    provincia: str
    municipio: str

class CapturaCreate(BaseModel):
    id_runner: int
    id_zona: int
    tipo_captura: str = "NORMAL"
    puntos_ganados: int = 10

# --- ENDPOINTS BÁSICOS ---
@app.get("/")
def raiz():
    return {"mensaje": "Servidor BattleRun Listo para la Batalla ⚔️"}

@app.post("/auth/registro", status_code=status.HTTP_201_CREATED)
def registrar_usuario(nuevo_usuario: RunnerCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        password_segura = encriptar_password(nuevo_usuario.password)
        sql = "INSERT INTO runner (email, password_hash, username, estado_cuenta) VALUES (%s, %s, %s, 'ACTIVA') RETURNING id_runner;"
        cur.execute(sql, (nuevo_usuario.email, password_segura, nuevo_usuario.username))
        id_gen = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"mensaje": "Usuario registrado", "id": id_gen, "usuario": nuevo_usuario.username}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
def login(datos_login: LoginRequest):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_runner, username, password_hash FROM runner WHERE email = %s", (datos_login.email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user or not verificar_password(datos_login.password, user[2]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        
        return {"mensaje": "Login OK", "usuario": {"id": user[0], "nombre": user[1]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/zonas")
def crear_zona(nueva_zona: ZonaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = "INSERT INTO zona (sistema_grid, codigo_celda, geometria, pais, provincia, municipio) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_zona;"
        cur.execute(sql, (nueva_zona.sistema_grid, nueva_zona.codigo_celda, nueva_zona.geometria, nueva_zona.pais, nueva_zona.provincia, nueva_zona.municipio))
        id_gen = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"mensaje": "Zona registrada", "id_zona": id_gen}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# --- AQUÍ ESTÁ LA NUEVA LÓGICA DE JUEGO ---

@app.post("/capturas")
def registrar_captura(datos: CapturaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # PASO 1: INVESTIGAR EL PASADO (¿De quién es esta zona ahora mismo?)
        # Buscamos la última captura de esta zona y hacemos un JOIN para saber el nombre del dueño
        sql_investigacion = """
            SELECT r.username 
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            WHERE cz.id_zona = %s
            ORDER BY cz.fecha_hora DESC
            LIMIT 1;
        """
        cur.execute(sql_investigacion, (datos.id_zona,))
        resultado_anterior = cur.fetchone()
        
        nombre_anterior_dueno = None
        if resultado_anterior:
            nombre_anterior_dueno = resultado_anterior[0]
            
        # PASO 2: REGISTRAR LA NUEVA CONQUISTA
        sql_insertar = """
            INSERT INTO captura_zona (id_runner, id_zona, fecha_hora, tipo_captura, puntos_ganados)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_captura;
        """
        ahora = datetime.datetime.now()
        cur.execute(sql_insertar, (datos.id_runner, datos.id_zona, ahora, datos.tipo_captura, datos.puntos_ganados))
        id_captura = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        # PASO 3: GENERAR EL MENSAJE DE BATALLA
        if nombre_anterior_dueno:
            if nombre_anterior_dueno == "Tú mismo (Front lo chequeará)": 
                # Lógica simplificada, aquí el front sabrá si es el mismo user por el ID
                mensaje = f"Has reforzado tu dominio sobre esta zona."
            else:
                mensaje = f"¡ATAQUE EXITOSO! ⚔️ Has arrebatado esta zona a {nombre_anterior_dueno}."
        else:
            mensaje = "¡NUEVO TERRITORIO! 🚩 Has reclamado una zona neutral."

        return {
            "mensaje": mensaje,
            "dueño_anterior": nombre_anterior_dueno,
            "puntos": datos.puntos_ganados,
            "fecha": ahora
        }
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    # --- ENDPOINTS DE RANKING (PROFESIONALES) ---

@app.get("/ranking/global")
def ranking_global():
    """Top 10 jugadores con más puntos en todo el juego"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql)
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {"titulo": "🏆 TOP MUNDIAL", "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ranking/pais/{pais}")
def ranking_pais(pais: str):
    """Top 10 jugadores con más puntos en un país concreto (ej: España)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Aquí hacemos un JOIN extra con la tabla ZONA para filtrar por 'pais'
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE z.pais = %s
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql, (pais,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {"titulo": f"🇪🇸 TOP {pais.upper()}", "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ranking/ciudad/{municipio}")
def ranking_ciudad(municipio: str):
    """Top 10 jugadores en una ciudad concreta (ej: Madrid)"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Filtramos por 'municipio'
        sql = """
            SELECT r.username, SUM(cz.puntos_ganados) as total
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE z.municipio = %s
            GROUP BY r.username
            ORDER BY total DESC
            LIMIT 10;
        """
        cur.execute(sql, (municipio,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        return {"titulo": f"🏙️ TOP {municipio.upper()}", "ranking": [{"pos": i+1, "user": r[0], "pts": r[1]} for i, r in enumerate(resultados)]}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))