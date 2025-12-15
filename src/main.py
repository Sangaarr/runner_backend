from fastapi import FastAPI, HTTPException
from database import get_db_connection

# 1. Creamos la aplicación
app = FastAPI(
    title="RunnerApp API",
    description="API para gestionar la aplicación de BattleRun",
    version="1.0.0"
)

# --- RUTAS (ENDPOINTS) ---

@app.get("/")
def raiz():
    """Ruta de bienvenida para verificar que el servidor funciona."""
    return {"mensaje": "¡Bienvenido a la API de RunnerApp! 🏃💨"}

@app.get("/runners")
def obtener_runners():
    """Devuelve la lista de todos los runners en la base de datos."""
    conn = get_db_connection()
    if not conn:
        # Si falla la DB, devolvemos un error 500 al usuario
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")

    try:
        cur = conn.cursor()
        cur.execute("SELECT id_runner, username, email, estado_cuenta FROM runner;")
        filas = cur.fetchall()
        
        # Convertimos las tuplas de la DB a un formato JSON bonito
        lista_runners = []
        for fila in filas:
            runner_dict = {
                "id": fila[0],
                "usuario": fila[1],
                "email": fila[2],
                "estado": fila[3]
            }
            lista_runners.append(runner_dict)
            
        cur.close()
        conn.close()
        return lista_runners

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))