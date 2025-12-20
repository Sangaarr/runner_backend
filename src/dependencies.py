from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
# En un proyecto real, esto iría en un archivo .env oculto
SECRET_KEY = "super_secreto_clave_maestra_battlerun" 
ALGORITHM = "HS256"

# Esto le dice a Swagger dónde está el endpoint de login para obtener el token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def crear_token_acceso(data: dict):
    """Crea un token que caduca en 7 días"""
    to_encode = data.copy()
    expiracion = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expiracion})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_runner_actual(token: str = Depends(oauth2_scheme)):
    """
    Esta función se usará en todos los endpoints protegidos.
    Valida el token y devuelve el ID del usuario (id_runner).
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_runner: int = payload.get("sub") # 'sub' es donde guardamos el ID
        if id_runner is None:
            raise HTTPException(status_code=401, detail="Token inválido: falta ID")
        return id_runner
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado, haz login de nuevo")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")