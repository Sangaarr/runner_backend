from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.database import get_db_connection
from src.dependencies import crear_token_acceso
import bcrypt
import datetime
import random
import string

router = APIRouter()

# --- MODELOS ---
class RunnerCreate(BaseModel):
    email: str
    password: str
    username: str

class LoginRequest(BaseModel):
    email: str
    password: str

# --- ÚTILES ---
def encriptar_password(password: str):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def verificar_password(password_plana, password_encriptada):
    return bcrypt.checkpw(password_plana.encode('utf-8'), password_encriptada.encode('utf-8'))

# --- ENDPOINTS ---
@router.post("/auth/registro", status_code=status.HTTP_201_CREATED)
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
        cur.close(); conn.close()
        return {"mensaje": "Usuario registrado", "id": id_gen, "usuario": nuevo_usuario.username}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login")
def login(datos_login: LoginRequest):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_runner, username, password_hash FROM runner WHERE email = %s", (datos_login.email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        
        if not user or not verificar_password(datos_login.password, user[2]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        
        # En lugar de solo devolver el ID, generamos el token
        id_runner = user[0]
        access_token = crear_token_acceso(data={"sub"str: id_runner, "name": user[1]})
        
        return {
            "mensaje": "Login exitoso",
            "access_token": access_token, 
            "token_type": "bearer",
            "usuario": {"id": id_runner, "nombre": user[1]}
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# MODELOS

class SolicitarRecuperacion(BaseModel):
    email: str

class CambiarPassword(BaseModel):
    email: str
    token: str  # Usamos tu nombre de columna
    nueva_password: str

# ENDPOINTS
@router.post("/auth/recuperar/solicitar")
def solicitar_recuperacion(datos: SolicitarRecuperacion):
    """Genera un token temporal para tu tabla recuperacion_cuenta"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # 1. Verificar runner
        cur.execute("SELECT id_runner FROM runner WHERE email = %s", (datos.email,))
        usuario = cur.fetchone()
        if not usuario: return {"mensaje": "Si el email existe, recibirás el código."}
        
        id_runner = usuario[0]
        # 2. Generar token corto (ej: AX9Z2)
        token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        
        # 3. Insertar usando TUS columnas (fecha_creacion es automática si la definiste así, sino usamos NOW())
        sql = "INSERT INTO recuperacion_cuenta (id_runner, token, fecha_creacion, usado) VALUES (%s, %s, NOW(), FALSE)"
        cur.execute(sql, (id_runner, token))
        conn.commit()
        cur.close(); conn.close()
        
        # DEBUG: Te devuelvo el token para probar. En prod, esto se envía por email.
        return {"mensaje": "Token generado (Debug)", "token_debug": token}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/recuperar/validar")
def restablecer_password(datos: CambiarPassword):
    """Valida el token (15 min validez) y cambia la password"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Buscar token válido no usado
        # Usamos tus columnas: token, fecha_creacion, usado
        sql = """
            SELECT r.id_runner, rc.fecha_creacion, rc.id_recuperacion
            FROM recuperacion_cuenta rc
            JOIN runner r ON rc.id_runner = r.id_runner
            WHERE r.email = %s AND rc.token = %s AND rc.usado = FALSE
            ORDER BY rc.fecha_creacion DESC LIMIT 1;
        """
        cur.execute(sql, (datos.email, datos.token))
        resultado = cur.fetchone()
        
        if not resultado: raise HTTPException(status_code=400, detail="Token inválido o email incorrecto")
        
        id_runner, fecha_creacion, id_recuperacion = resultado
        
        # 2. Verificar expiración en Python (15 minutos desde fecha_creacion)
        # Aseguramos que ambas fechas tengan zona horaria o sean ingenuas (naive)
        ahora = datetime.datetime.now()
        if fecha_creacion.tzinfo is not None:
             ahora = ahora.astimezone(fecha_creacion.tzinfo)

        if ahora > (fecha_creacion + datetime.timedelta(minutes=15)):
             raise HTTPException(status_code=400, detail="El token ha caducado.")

        # 3. Cambiar password y marcar token
        nueva_pass_hash = encriptar_password(datos.nueva_password)
        cur.execute("UPDATE runner SET password_hash = %s WHERE id_runner = %s", (nueva_pass_hash, id_runner))
        # Actualizamos usado y fecha_uso
        cur.execute("UPDATE recuperacion_cuenta SET usado = TRUE, fecha_uso = NOW() WHERE id_recuperacion = %s", (id_recuperacion,))
        
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "¡Contraseña restablecida! Ya puedes hacer login."}
        
    except Exception as e:
        if conn: conn.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))