from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.database import get_db_connection
import bcrypt

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
        
        return {"mensaje": "Login OK", "usuario": {"id": user[0], "nombre": user[1]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))