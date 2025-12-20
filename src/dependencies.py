from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
SECRET_KEY = "super_secreto_clave_maestra_battlerun" 
ALGORITHM = "HS256"

# CAMBIO CLAVE: Usamos HTTPBearer para que Swagger nos deje pegar el token manualmente
security = HTTPBearer()

def crear_token_acceso(data: dict):
    """Crea un token que caduca en 7 días"""
    to_encode = data.copy()
    expiracion = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expiracion})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_runner_actual(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Valida el token y devuelve el ID del usuario.
    Ahora extraemos el token del objeto 'credentials'.
    """
    token = credentials.credentials  # <--- Aquí sacamos el string del token
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_runner: int = payload.get("sub")
        if id_runner is None:
            raise HTTPException(status_code=401, detail="Token inválido: falta ID")
        return id_runner
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado, haz login de nuevo")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")