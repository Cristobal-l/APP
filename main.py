import os
import io
import time
import base64
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import uvicorn
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client

load_dotenv()

# --- MODELOS ---
class UsuarioRequest(BaseModel):
    nombre: str
    correo: str
    contrasena: str

class LoginRequest(BaseModel):
    correo: str
    contrasena: str

class MensajeRequest(BaseModel):
    texto: str
    id_usuario: str

class DispositivoRequest(BaseModel):
    id_usuario: str
    nombre: str = 'V.I.A ESP32'
    bateria: int
    conectado: bool = False

class HeartbeatRequest(BaseModel):
    bateria: Optional[int] = None

# --- APP ---
app = FastAPI(title="Servidor de Visión VIA - Producción (Render)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CLIENTES ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- ESTADO MEMORIA (VISIÓN) ---
ESTADO_ACTUAL = {
    "descripcion": "Esperando la primera conexión del ESP32...",
    "timestamp": 0
}
NOMBRE_ARCHIVO_STORAGE = "latest.jpg"

# --- ENDPOINTS USUARIOS ---
@app.get("/")
def bienvenida():
    return {"mensaje": "backend funcionando en Render."}

@app.post("/registro")
def registrar_usuario(nuevo_usuario: UsuarioRequest):
    try:
        existente = supabase.table("usuario").select("id").eq("correo", nuevo_usuario.correo).execute()
        if existente.data:
            return {"estado": "error", "mensaje": "El correo ya está registrado"}
        supabase.table("usuario").insert(nuevo_usuario.model_dump()).execute()
        return {"estado": "exito", "mensaje": f"Usuario {nuevo_usuario.nombre} registrado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
def iniciar_sesion(credenciales: LoginRequest):
    try:
        llamada = supabase.table("usuario").select("id", "nombre").eq("correo", credenciales.correo).eq("contrasena", credenciales.contrasena).execute()
        if llamada.data:
            return {"estado": "exito", "usuario": llamada.data[0]}
        return {"estado": "error", "mensaje": "Correo o contraseña incorrectos"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mensaje")
def recibir_mensaje(msg: MensajeRequest):
    try:
        supabase.table("mensaje").insert(msg.model_dump()).execute()
        return {"estado": "exito"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/historial/{id_usuario}")
def obtener_historial(id_usuario: str):
    try:
        resultado = supabase.table("mensaje").select("*").eq("id_usuario", id_usuario).execute()
        return resultado.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS ESP32 ---
@app.post("/esp32/heartbeat")
def esp32_heartbeat(datos: HeartbeatRequest = None):
    try:
        update_data = {"ultimo_ping": "now()", "conectado": True}
        if datos and datos.bateria is not None:
            update_data["bateria"] = datos.bateria
        existente = supabase.table("dispositivo").select("id").limit(1).execute()
        if existente.data:
            supabase.table("dispositivo").update(update_data).eq("id", existente.data[0]["id"]).execute()
        return {"estado": "ok", "mensaje": "Latido recibido"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/esp32/status")
def obtener_estado_esp32():
    try:
        resultado = supabase.table("dispositivo").select("*").limit(1).execute()
        if not resultado.data:
            return {"activo": False, "mensaje": "El dispositivo nunca se ha conectado.", "bateria": None}
        
        dispositivo = resultado.data[0]
        ultimo_ping = dispositivo.get("ultimo_ping")
        bateria = dispositivo.get("bateria")
        conectado = dispositivo.get("conectado", False)

        return {
            "activo": conectado,
            "mensaje": "Dispositivo activo" if conectado else "Sin conexión",
            "bateria": bateria,
            "ultimo_ping": ultimo_ping
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- LÓGICA DE VISIÓN (OPENAI) ---
def optimizar_desde_bytes(datos_binarios: bytes, modo: str = "calle") -> bytes:
    try:
        img = Image.open(io.BytesIO(datos_binarios))
        # Rotar la imagen 90 grados a la izquierda (sentido antihorario)
        img = img.rotate(90, expand=True)
        # Espejo horizontal para corregir izquierda/derecha desde la perspectiva del usuario
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        
        # FIX #7: Crop central en modo calle para reducir el FOV
        # Recortar el 70% central de la imagen para simular zoom y dar más detalle de lo de enfrente
        if modo == "calle":
            w, h = img.size
            crop_ratio = 0.7  # Mantener el 70% central (más contexto que antes)
            new_w = int(w * crop_ratio)
            new_h = int(h * crop_ratio)
            left = (w - new_w) // 2
            top = (h - new_h) // 2
            img = img.crop((left, top, left + new_w, top + new_h))
        
        img.thumbnail((512, 512))  # Mayor resolución para mejor detección de escaleras y superficies
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)  # Mayor calidad para preservar detalles
        return buffer.getvalue()
    except Exception as e:
        print(f"Error al optimizar imagen: {e}")
        raise HTTPException(status_code=400, detail="Error al procesar el formato de la imagen.")

def procesar_imagen_directo(img_bytes_opt: bytes, user_id: str = None, modo: str = "calle") -> str:
    try:
        img_b64 = base64.b64encode(img_bytes_opt).decode('utf-8')
        
        if modo == "casa":
            # Prompt modo casa - detección de obstáculos, escaleras, y objetos a nivel cabeza
            prompt = (
                "Eres un asistente de movilidad para una persona ciega dentro de un edificio o casa. "
                "Analiza la imagen con EXTREMO CUIDADO en el siguiente orden de prioridad:\n"
                "1) SUELO Y SUPERFICIE: ¿Hay escaleras (subiendo o bajando), escalones, rampas, desniveles, "
                "o cambios de altura en el piso? Si ves líneas horizontales paralelas que forman peldaños, "
                "SON ESCALERAS, no un 'camino liso'. Indica si suben o bajan y cuántos peldaños aproximados.\n"
                "2) OBSTÁCULOS A NIVEL DE CABEZA: Lámparas bajas, marcos de puerta, estantes salientes, "
                "ventiladores de techo, ropa colgada, cables.\n"
                "3) OBSTÁCULOS EN EL SUELO: Cables, objetos tirados, alfombras arrugadas, muebles bajos.\n"
                "4) ESPACIO: ¿Hay puerta, pasillo, o pared al frente? ¿A qué distancia aproximada?\n"
                "Usa referencias de tamaño (comparando con puertas, personas, muebles) para estimar alturas y distancias. "
                "Responde en máximo 3 oraciones cortas en español. Sé MUY específico con escaleras y desniveles."
            )
            max_tok = 180
        else:
            # Prompt modo calle - navegación exterior con detección precisa de superficies
            prompt = (
                "Eres un asistente de navegación para una persona ciega caminando por la calle. "
                "La imagen muestra lo que está DIRECTAMENTE AL FRENTE del usuario. "
                "Analiza con MÁXIMA PRECISIÓN en este orden:\n"
                "1) SUPERFICIE DEL SUELO: ¿Es vereda lisa, adoquines, tierra, pasto, asfalto? "
                "¿HAY ESCALERAS, GRADAS O PELDAÑOS? Si ves líneas horizontales con sombras que forman escalones, "
                "di EXACTAMENTE 'hay escaleras' e indica si suben o bajan y cuántos peldaños aproximados. "
                "¿Hay rampas, baches, hoyos, cordones de vereda, o desniveles? NUNCA digas 'camino liso' "
                "si hay cualquier cambio de nivel visible.\n"
                "2) OBSTÁCULOS: ¿Qué hay al frente? (pared, reja, poste, vehículo, persona, árbol, banca). "
                "Indica la dirección (izquierda, derecha, al frente) y distancia aproximada. "
                "NUNCA digas 'camino despejado' si hay un objeto sólido a menos de 3 metros.\n"
                "3) TEXTO VISIBLE: Lee COMPLETO cualquier letrero, cartel, señal de tránsito, "
                "nombre de calle o número de bus visible.\n"
                "4) ALTURA: Si hay objetos elevados (ramas bajas, toldos, señales), estima la altura "
                "usando referencias como puertas (~2m), personas (~1.7m), o postes.\n"
                "Responde en máximo 3 oraciones cortas en español. Sé PRECISO con las superficies."
            )
            max_tok = 200
            
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": prompt
                        },
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}
                        },
                    ],
                }
            ],
            max_tokens=max_tok
        )
        descripcion = response.choices[0].message.content
        print(f"Resultado IA:\n{descripcion}")
        
        ESTADO_ACTUAL["descripcion"] = descripcion
        ESTADO_ACTUAL["timestamp"] = time.time()
        
        # --- NUEVA LOGICA: Guardar en la tabla 'mensaje' con el id_usuario recibido ---
        try:
            if user_id:
                supabase.table("mensaje").insert({
                    "texto": descripcion, 
                    "id_usuario": user_id
                }).execute()
                print("Mensaje de IA guardado con éxito vinculándolo al usuario.")
            else:
                print("Advertencia: No se recibió ningún id_usuario de la app, el mensaje no se guardó en BD.")
        except Exception as db_e:
            print(f"Error guardando en la tabla mensaje: {db_e}")
            
        return descripcion
    except Exception as e:
        print(f"Error en IA: {e}")
        error_msg = "Error al analizar la imagen con OpenAI."
        ESTADO_ACTUAL["descripcion"] = error_msg
        ESTADO_ACTUAL["timestamp"] = time.time()
        return error_msg

# --- ENDPOINTS VISIÓN ---
@app.post("/upload", response_class=PlainTextResponse)
async def upload(request: Request):
    img_data = await request.body()
    if not img_data:
        raise HTTPException(status_code=400, detail="No hay datos binarios")

    user_id = request.headers.get("x-user-id")
    modo = request.headers.get("x-modo", "calle")

    bytes_optimizados = optimizar_desde_bytes(img_data, modo)

    try:
        supabase.storage.from_("fotos").upload(
            NOMBRE_ARCHIVO_STORAGE,
            bytes_optimizados,
            {"content-type": "image/jpeg", "upsert": "true"}
        )
    except Exception as e:
        print(f"No se pudo subir al Storage de Supabase: {e}")
        
    ESTADO_ACTUAL["descripcion"] = "Procesando nueva imagen..."
    ESTADO_ACTUAL["timestamp"] = time.time()

    resultado_ia = procesar_imagen_directo(bytes_optimizados, user_id, modo)
    return resultado_ia 

@app.get("/latest-info")
def get_latest_info():
    return JSONResponse(content=ESTADO_ACTUAL)

@app.get("/latest-image")
def get_latest_image():
    try:
        res = supabase.storage.from_("fotos").get_public_url(NOMBRE_ARCHIVO_STORAGE)
        return RedirectResponse(url=res)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No se pudo obtener la imagen: {e}")

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)