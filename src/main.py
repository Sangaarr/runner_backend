from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from database import get_db_connection
import bcrypt  # <--- CAMBIO: Usamos bcrypt directamente, sin passlib
import datetime

app = FastAPI(
    title="RunnerApp API",
    description="Backend Seguro para BattleRun Mobile",
    version="2.1.0"
)

# --- CONFIGURACIÓN DE SEGURIDAD (CORREGIDA) ---

def encriptar_password(password: str):
    # 1. Convertimos el texto a bytes (ordenador entiende bytes)
    password_bytes = password.encode('utf-8')
    # 2. Generamos la sal (salt) y el hash
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # 3. Lo devolvemos como texto para guardarlo en la base de datos Postgres
    return hashed_bytes.decode('utf-8')

def verificar_password(password_plana, password_encriptada):
    # Convertimos ambos a bytes para compararlos
    password_plana_bytes = password_plana.encode('utf-8')
    password_encriptada_bytes = password_encriptada.encode('utf-8')
    
    return bcrypt.checkpw(password_plana_bytes, password_encriptada_bytes)

# --- MODELOS DE DATOS ---

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

# --- ENDPOINTS ---

@app.get("/")
def raiz():
    return {"mensaje": "Servidor BattleRun Seguro 🔒"}

# --- 1. REGISTRO SEGURO ---
@app.post("/auth/registro", status_code=status.HTTP_201_CREATED)
def registrar_usuario(nuevo_usuario: RunnerCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # ENCRIPTAMOS la contraseña usando la nueva función
        password_segura = encriptar_password(nuevo_usuario.password)
        
        sql = """
            INSERT INTO runner (email, password_hash, username, estado_cuenta)
            VALUES (%s, %s, %s, 'ACTIVA')
            RETURNING id_runner;
        """
        cur.execute(sql, (nuevo_usuario.email, password_segura, nuevo_usuario.username))
        
        id_gen = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"mensaje": "Usuario registrado exitosamente", "id": id_gen, "usuario": nuevo_usuario.username}
        
    except Exception as e:
        if conn: conn.rollback()
        # Imprimimos el error real en la consola para que lo veas si vuelve a fallar
        print(f"ERROR DETALLADO: {e}") 
        raise HTTPException(status_code=400, detail=f"Error en registro: {str(e)}")

# --- 2. LOGIN REAL (VERIFICACIÓN) ---
@app.post("/auth/login")
def login(datos_login: LoginRequest):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # Buscamos al usuario
        sql = "SELECT id_runner, username, password_hash FROM runner WHERE email = %s"
        cur.execute(sql, (datos_login.email,))
        usuario_encontrado = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not usuario_encontrado:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        id_user = usuario_encontrado[0]
        nombre = usuario_encontrado[1]
        hash_guardado = usuario_encontrado[2]
        
        # Verificamos con la nueva función directa
        if not verificar_password(datos_login.password, hash_guardado):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        
        return {
            "mensaje": "¡Login Correcto! 🔓",
            "token_falso": "token_jwt_simulado_123456", 
            "usuario": {
                "id": id_user,
                "nombre": nombre,
                "email": datos_login.email
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"ERROR LOGIN: {e}")
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")

# --- RUTAS DE ZONAS Y CAPTURAS (IGUAL QUE ANTES) ---

@app.post("/zonas")
def crear_zona(nueva_zona: ZonaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO zona (sistema_grid, codigo_celda, geometria, pais, provincia, municipio)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_zona;
        """
        cur.execute(sql, (nueva_zona.sistema_grid, nueva_zona.codigo_celda, nueva_zona.geometria, nueva_zona.pais, nueva_zona.provincia, nueva_zona.municipio))
        id_zona = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"mensaje": "Zona registrada", "id_zona": id_zona}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/capturas")
def registrar_captura(datos: CapturaCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO captura_zona (id_runner, id_zona, fecha_hora, tipo_captura, puntos_ganados)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_captura;
        """
        cur.execute(sql, (datos.id_runner, datos.id_zona, datetime.datetime.now(), datos.tipo_captura, datos.puntos_ganados))
        id_captura = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"mensaje": "Territorio conquistado", "id_captura": id_captura}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))