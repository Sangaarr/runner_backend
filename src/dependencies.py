from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
# ASEGÚRATE DE QUE ESTA CLAVE SEA EXACTAMENTE LA MISMA QUE USAS AL CREAR EL TOKEN
SECRET_KEY = "super_secreto_clave_maestra_battlerun" 
ALGORITHM = "HS256"

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
    """
    token = credentials.credentials
    
    # --- DEBUG: IMPRIMIMOS LO QUE LLEGA ---
    print(f"\n🔍 DEBUG - Token recibido: '{token}'") 
    
    try:
        # Intentamos decodificar
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_runner: int = payload.get("sub")
        
        if id_runner is None:
            raise HTTPException(status_code=401, detail="Token válido pero falta el ID (sub)")
            
        return id_runner

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado (Expired)")
        
    except jwt.PyJWTError as e:
        # --- DEBUG: IMPRIMIMOS EL ERROR REAL ---
        print(f"❌ DEBUG - Error JWT: {str(e)}")
        
        # Le devolvemos el error técnico a Swagger para que lo leas
        raise HTTPException(status_code=401, detail=f"Token inválido (Error técnico: {str(e)})")