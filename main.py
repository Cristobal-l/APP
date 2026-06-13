import os
import io
import time
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import uvicorn
from pydantic import BaseModel
from typing import Optional
from supabase import create_client

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
app = FastAPI(title="Servidor de Visión VIA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CLIENTES ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = genai.GenerativeModel("gemini-2.0-flash")
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# --- ENDPOINTS USUARIOS ---
@app.get("/")
def bienvenida():
    return {"mensaje": "backend funcionando."}

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
        # Buscar si existe un dispositivo
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

# --- ENDPOINTS VISIÓN ---
def procesar_imagen_en_fondo(img_data: bytes, nombre_archivo: str):
    try:
        img = Image.open(io.BytesIO(img_data))
        img.thumbnail((320, 320))

        # Subir imagen a Supabase Storage
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)
        supabase.storage.from_("fotos").upload(
            nombre_archivo,
            buffer.read(),
            {"content-type": "image/jpeg", "upsert": "true"}
        )

        # Procesar con Gemini
        img_gemini = Image.open(io.BytesIO(img_data))
        img_gemini.thumbnail((320, 320))
        response = client.generate_content([
            "Actua como guia para un ciego en máximo 2 oraciones. Indica: peligros u obstáculos en la trayectoria, objetos relevantes, semáforos, señales o texto visible.",
            img_gemini
        ])

        descripcion = response.text
        print(f"Resultado IA:\n{descripcion}")

        # Guardar descripción en Supabase
        supabase.table("descripcion").insert({
            "texto": descripcion
        }).execute()

    except Exception as e:
        print(f"Error en IA: {e}")
        supabase.table("descripcion").insert({
            "texto": "Error al analizar la imagen."
        }).execute()

@app.post("/upload", response_class=PlainTextResponse)
async def upload(request: Request, background_tasks: BackgroundTasks):
    img_data = await request.body()
    if not img_data:
        raise HTTPException(status_code=400, detail="No hay datos")
    background_tasks.add_task(procesar_imagen_en_fondo, img_data, "latest.jpg")
    return "OK"

@app.get("/latest-info")
def get_latest_info():
    try:
        resultado = supabase.table("descripcion").select("*").order("timestamp", desc=True).limit(1).execute()
        if resultado.data:
            desc = resultado.data[0]
            return JSONResponse(content={
                "descripcion": desc["texto"],
                "timestamp": desc["timestamp"]
            })
        return JSONResponse(content={
            "descripcion": "Esperando la primera conexión del ESP32...",
            "timestamp": None
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/latest-image")
def get_latest_image():
    try:
        url = supabase.storage.from_("fotos").get_public_url("latest.jpg")
        return JSONResponse(content={"url": url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)