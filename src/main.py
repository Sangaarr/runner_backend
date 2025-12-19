from fastapi import FastAPI
from src.routers import auth, logros, mapas, temporadas, ranking, capturas, social

app = FastAPI(
    title="RunnerApp API",
    description="Backend BattleRun - Lógica de Juego Activa ⚔️",
    version="2.3.0"
)

# --- CONEXIÓN DE ROUTERS (Los módulos del juego) ---
app.include_router(auth.router)       # Login y Registro
app.include_router(mapas.router)      # Zonas y Mapas
app.include_router(capturas.router)   # Batallas y Capturas
app.include_router(logros.router)     # Medallas
app.include_router(ranking.router)    # Clasificaciones
app.include_router(social.router)     # Equipos, Amigos y Notificaciones
app.include_router(temporadas.router) # (Futuro)

# --- ENDPOINT DE SALUD ---
@app.get("/")
def raiz():
    return {"mensaje": "Servidor BattleRun Operativo y Listo ⚔️"}