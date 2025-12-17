from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from src.database import get_db_connection
import bcrypt
import datetime
from src.routers import logros # Importamos el archivo entero

app = FastAPI(
    title="RunnerApp API",
    description="Backend BattleRun - Lógica de Juego Activa ⚔️",
    version="2.2.0"
)

app.include_router(logros.router)

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
        hubo_premio = logros.verificar_y_otorgar_logros(datos.id_runner, conn)
        
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
        if hubo_premio:
            mensaje += " ¡Y has desbloqueado un NUEVO LOGRO! 🏅"

    return {"mensaje": mensaje, "puntos_ganados": datos.puntos_ganados, "id_captura": id_captura}


        
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
    
    # --- MODELOS PARA EQUIPOS ---
class EquipoCreate(BaseModel):
    nombre: str
    descripcion: str
    ciudad_base: str

class UnirseEquipoRequest(BaseModel):
    id_runner: int
    id_equipo: int

# --- ENDPOINTS DE EQUIPOS ---

@app.post("/equipos")
def crear_equipo(equipo: EquipoCreate):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO equipo (nombre, descripcion, ciudad_base)
            VALUES (%s, %s, %s)
            RETURNING id_equipo;
        """
        cur.execute(sql, (equipo.nombre, equipo.descripcion, equipo.ciudad_base))
        id_equipo = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        
        return {"mensaje": "¡Equipo Fundado! 🛡️", "id_equipo": id_equipo, "nombre": equipo.nombre}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/equipos/unirse")
def unirse_equipo(datos: UnirseEquipoRequest):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. Verificar si ya está en ese equipo (Opcional, pero recomendado)
        # 2. Insertar en la tabla intermedia 'runner_equipo'
        # Asumimos rol 'Miembro' por defecto
        sql = """
            INSERT INTO runner_equipo (id_runner, id_equipo, rol, fecha_union)
            VALUES (%s, %s, 'Miembro', %s)
            RETURNING fecha_union;
        """
        ahora = datetime.datetime.now()
        cur.execute(sql, (datos.id_runner, datos.id_equipo, ahora))
        
        conn.commit()
        cur.close(); conn.close()
        
        return {
            "mensaje": "¡Te has unido al equipo! 🤝",
            "equipo_id": datos.id_equipo,
            "usuario_id": datos.id_runner
        }
        
    except Exception as e:
        if conn: conn.rollback()
        # Este error salta si el usuario ya está en el equipo (violación de clave primaria compuesta)
        raise HTTPException(status_code=400, detail=f"No puedes unirte (¿Ya estás dentro?): {str(e)}")

@app.get("/equipos/{id_equipo}/miembros")
def ver_miembros_equipo(id_equipo: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Hacemos un JOIN para sacar los nombres de los runners de ese equipo
        sql = """
            SELECT r.username, re.rol, re.fecha_union
            FROM runner_equipo re
            JOIN runner r ON re.id_runner = r.id_runner
            WHERE re.id_equipo = %s;
        """
        cur.execute(sql, (id_equipo,))
        miembros = cur.fetchall()
        cur.close(); conn.close()
        
        lista = [{"usuario": m[0], "rol": m[1], "desde": m[2]} for m in miembros]
        return {"id_equipo": id_equipo, "total_miembros": len(lista), "miembros": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    # --- MODELOS SOCIALES ---
class SeguirRequest(BaseModel):
    id_seguidor: int
    id_seguido: int

# --- ENDPOINTS SOCIALES (ADAPTADOS A TU DB REAL) ---

@app.post("/social/seguir")
def seguir_usuario(datos: SeguirRequest):
    if datos.id_seguidor == datos.id_seguido:
        raise HTTPException(status_code=400, detail="No puedes seguirte a ti mismo")
        
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # 1. INSERTAR EN TABLA 'seguidor'
        # Asumiendo columnas: id_seguidor, id_seguido, fecha_desde
        sql_seguir = """
            INSERT INTO seguidor (id_seguidor, id_seguido, fecha_desde)
            VALUES (%s, %s, %s);
        """
        ahora = datetime.datetime.now()
        cur.execute(sql_seguir, (datos.id_seguidor, datos.id_seguido, ahora))
        
        # 2. INSERTAR EN TABLA 'notificacion'
        # Usamos TUS columnas exactas: id_runner, tipo, titulo, mensaje, leida, fecha_hora
        sql_notif = """
            INSERT INTO notificacion (id_runner, tipo, titulo, mensaje, leida, fecha_hora)
            VALUES (%s, 'SOCIAL', 'Nuevo Seguidor', '¡Alguien ha empezado a seguirte!', FALSE, %s);
        """
        cur.execute(sql_notif, (datos.id_seguido, ahora))
        
        conn.commit()
        cur.close(); conn.close()
        return {"mensaje": "¡Ahora sigues a este usuario! 👀"}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error (¿Ya lo sigues?): {str(e)}")

@app.get("/social/feed/{id_mi_usuario}")
def obtener_feed_amigos(id_mi_usuario: int):
    """Muestra las capturas de la gente a la que sigues"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, z.municipio, cz.puntos_ganados, cz.fecha_hora, cz.tipo_captura
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            JOIN zona z ON cz.id_zona = z.id_zona
            WHERE cz.id_runner IN (
                SELECT id_seguido FROM seguidor WHERE id_seguidor = %s
            )
            ORDER BY cz.fecha_hora DESC
            LIMIT 20;
        """
        cur.execute(sql, (id_mi_usuario,))
        feed = cur.fetchall()
        cur.close(); conn.close()
        
        feed_list = []
        for item in feed:
            feed_list.append({
                "usuario": item[0],
                "accion": f"Conquistó una zona en {item[1]}",
                "puntos": item[2],
                "cuando": item[3],
                "tipo": item[4]
            })
            
        return {"feed": feed_list}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notificaciones/{id_usuario}")
def ver_notificaciones(id_usuario: int):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Seleccionamos las columnas que existen en tu imagen
        sql = """
            SELECT tipo, titulo, mensaje, fecha_hora, leida 
            FROM notificacion 
            WHERE id_runner = %s 
            ORDER BY fecha_hora DESC
        """
        cur.execute(sql, (id_usuario,))
        notis = cur.fetchall()
        
        # Marcar como leídas
        cur.execute("UPDATE notificacion SET leida = TRUE WHERE id_runner = %s", (id_usuario,))
        conn.commit()
        
        cur.close(); conn.close()
        
        lista = []
        for n in notis:
            lista.append({
                "tipo": n[0],      # Columna 'tipo'
                "titulo": n[1],    # Columna 'titulo'
                "mensaje": n[2],   # Columna 'mensaje'
                "fecha": n[3],     # Columna 'fecha_hora'
                "nueva": not n[4]  # Columna 'leida' (si es False, es nueva)
            })
            
        return {"tus_notificaciones": lista}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    # --- ENDPOINTS DE PERFIL SOCIAL (LISTAS) ---

@app.get("/social/seguidores/{id_usuario}")
def ver_quien_me_sigue(id_usuario: int):
    """Devuelve la lista de personas que siguen al usuario"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Buscamos en la tabla 'seguidor' donde yo soy el 'id_seguido'
        # Hacemos JOIN con runner para saber sus nombres
        sql = """
            SELECT r.username, s.fecha_desde
            FROM seguidor s
            JOIN runner r ON s.id_seguidor = r.id_runner
            WHERE s.id_seguido = %s;
        """
        cur.execute(sql, (id_usuario,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        lista = [{"usuario": r[0], "desde": r[1]} for r in resultados]
        
        return {
            "total_seguidores": len(lista),
            "lista": lista
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/social/siguiendo/{id_usuario}")
def ver_a_quien_sigo(id_usuario: int):
    """Devuelve la lista de personas a las que el usuario sigue"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Buscamos donde yo soy el 'id_seguidor' (el que da el follow)
        sql = """
            SELECT r.username, s.fecha_desde
            FROM seguidor s
            JOIN runner r ON s.id_seguido = r.id_runner
            WHERE s.id_seguidor = %s;
        """
        cur.execute(sql, (id_usuario,))
        resultados = cur.fetchall()
        cur.close(); conn.close()
        
        lista = [{"usuario": r[0], "desde": r[1]} for r in resultados]
        
        return {
            "total_siguiendo": len(lista),
            "lista": lista
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    # --- ENDPOINTS DE MAPA Y ESTADO DE ZONAS ---

@app.get("/zonas/mapa/estado")
def obtener_estado_mapa():
    """
    Devuelve la lista de TODAS las zonas y quién es el dueño actual.
    Ideal para pintar el mapa de colores en la App.
    """
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        
        # Truco PRO de SQL (DISTINCT ON):
        # Seleccionamos cada zona (z.id_zona) y la ordenamos por fecha DESC.
        # Postgres se queda solo con la primera fila de cada grupo (la captura más reciente).
        # Usamos LEFT JOIN para que también salgan las zonas que NADIE ha capturado todavía (saldrán con NULL).
        
        sql = """
            SELECT DISTINCT ON (z.id_zona)
                z.id_zona,
                z.municipio, 
                r.username, 
                cz.fecha_hora
            FROM zona z
            LEFT JOIN captura_zona cz ON z.id_zona = cz.id_zona
            LEFT JOIN runner r ON cz.id_runner = r.id_runner
            ORDER BY z.id_zona, cz.fecha_hora DESC;
        """
        
        cur.execute(sql)
        zonas = cur.fetchall()
        cur.close(); conn.close()
        
        lista_mapa = []
        for z in zonas:
            dueno = z[2] if z[2] else "ZONA NEUTRAL" # Si es None, es neutral
            lista_mapa.append({
                "id_zona": z[0],
                "municipio": z[1],
                "propietario": dueno,
                "conquistada_el": z[3]
            })
            
        return {"total_zonas": len(lista_mapa), "mapa": lista_mapa}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/zonas/{id_zona}/info")
def info_zona_detalle(id_zona: int):
    """Devuelve el dueño actual de UNA zona específica"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT r.username, cz.fecha_hora
            FROM captura_zona cz
            JOIN runner r ON cz.id_runner = r.id_runner
            WHERE cz.id_zona = %s
            ORDER BY cz.fecha_hora DESC
            LIMIT 1;
        """
        cur.execute(sql, (id_zona,))
        resultado = cur.fetchone()
        cur.close(); conn.close()
        
        if resultado:
            return {"estado": "OCUPADA", "propietario": resultado[0], "fecha": resultado[1]}
        else:
            return {"estado": "LIBRE", "mensaje": "Esta zona es neutral. ¡Corre a por ella!"}
            
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/logros")
def listar_logros_disponibles():
    """Muestra todas las medallas disponibles con sus iconos y categorías"""
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Sin conexión DB")
    
    try:
        cur = conn.cursor()
        # Seleccionamos las columnas que SI existen en tu foto
        cur.execute("SELECT id_logro, nombre, descripcion, icono, categoria FROM logro")
        logros = cur.fetchall()
        cur.close(); conn.close()
        
        lista = []
        for l in logros:
            lista.append({
                "id": l[0], 
                "titulo": l[1], 
                "descripcion": l[2], 
                "icono": l[3],       # Nuevo campo
                "categoria": l[4]    # Nuevo campo
            })
            
        return lista
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))