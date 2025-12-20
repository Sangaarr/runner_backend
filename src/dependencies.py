from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
SECRET_KEY = "super_secreto_clave_maestra_battlerun" 
ALGORITHM = "HS256"

security = HTTPBearer()

def crear_token_acceso(data: dict):
    """Crea un token JWT que caduca en 7 días."""
    to_encode = data.copy()
    expiracion = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expiracion})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_runner_actual(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Valida el token Bearer y devuelve el ID del usuario.
    Si el token es inválido o ha expirado, lanza una excepción 401.
    """
    token = credentials.credentials
    
    try:
        # Decodificamos el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Recuperamos el ID (viene como string, lo pasamos a int)
        sub_texto = payload.get("sub")
        if sub_texto is None:
            raise HTTPException(status_code=401, detail="Token inválido")
            
        return int(sub_texto)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado")
    except (jwt.PyJWTError, ValueError):
        # Capturamos cualquier otro error (firma mala, formato incorrecto, etc.)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")