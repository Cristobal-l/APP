import os
import io
import base64
import time
from supabase import create_client, Client
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import uvicorn

# Cargar variables de entorno
load_dotenv()

# Inicializar clientes
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI(title="Servidor de Visión VIA - Vercel")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global en memoria para descripciones (Vercel lo mantiene mientras la función esté activa)
ESTADO_ACTUAL = {
    "descripcion": "Esperando la primera conexión del ESP32...",
    "timestamp": 0
}
NOMBRE_ARCHIVO_STORAGE = "latest.jpg"


def optimizar_desde_bytes(datos_binarios: bytes) -> bytes:
    """Redimensiona la imagen para reducir la latencia y optimizar el envío."""
    try:
        img = Image.open(io.BytesIO(datos_binarios))
        img.thumbnail((320, 320)) 
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()
    except Exception as e:
        print(f"❌ Error al optimizar imagen: {e}")
        raise HTTPException(status_code=400, detail="Error al procesar el formato de la imagen.")


def procesar_imagen_directo(img_bytes_opt: bytes) -> str:
    """Envía la imagen a OpenAI de forma síncrona y guarda el resultado."""
    try:
        # Convertir los bytes optimizados a Base64 para la API de OpenAI
        img_b64 = base64.b64encode(img_bytes_opt).decode('utf-8')
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Actua como guia para un ciego y rellena la siguiente plantilla: peligros:[describir] o objetos relevantes:[listar], obstaculos (si es etiqueta explicala, si es libro leelo)."
                        },
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "low"}
                        },
                    ],
                }
            ],
            max_tokens=100
        )
        
        descripcion = response.choices[0].message.content
        print(f"📝 Resultado IA:\n{descripcion}")
        
        # Actualizar el estado global en memoria
        ESTADO_ACTUAL["descripcion"] = descripcion
        ESTADO_ACTUAL["timestamp"] = time.time()
        
        # Guardar el historial en la base de datos de Supabase
        supabase.table("mensaje").insert({
            "texto": descripcion, 
            "id_usuario": "09f20151-a8d9-45a0-a6d0-b2be0cf71a53"
        }).execute()
        
        return descripcion

    except Exception as e:
        print(f"❌ Error en IA: {e}")
        error_msg = "Error al analizar la imagen con OpenAI."
        ESTADO_ACTUAL["descripcion"] = error_msg
        ESTADO_ACTUAL["timestamp"] = time.time()
        return error_msg


# --- ENDPOINT DE CARGA SÍNCRONO (PARA FLUTTER) ---
@app.post("/upload", response_class=PlainTextResponse)
async def upload(request: Request):
    """
    Recibe los bytes binarios desde Flutter, optimiza la imagen, 
    la sube a Supabase Storage, invoca a OpenAI y retorna la descripción.
    """
    img_data = await request.body()
    if not img_data:
        raise HTTPException(status_code=400, detail="No hay datos binarios en la petición.")

    # 1. Optimizar la imagen en memoria
    bytes_optimizados = optimizar_desde_bytes(img_data)

    # 2. Subir de forma segura al Storage de Supabase (Evita usar el disco duro de Vercel)
    try:
        supabase.storage.from_("fotos").upload(
            NOMBRE_ARCHIVO_STORAGE,
            bytes_optimizados,
            {"content-type": "image/jpeg", "upsert": "true"} # 'upsert: true' sobrescribe el archivo anterior
        )
    except Exception as e:
        print(f"⚠️ No se pudo subir al Storage de Supabase: {e}")
        
    ESTADO_ACTUAL["descripcion"] = "🧠 Procesando nueva imagen, por favor espera..."
    ESTADO_ACTUAL["timestamp"] = time.time()

    # 3. Obtener respuesta de OpenAI en tiempo real
    resultado_ia = procesar_imagen_directo(bytes_optimizados)
    
    # Flutter recibe el String directo para su TTS
    return resultado_ia 


# --- RUTAS PARA EL FRONTEND DE REACT ---
@app.get("/latest-info")
def get_latest_info():
    """Devuelve el JSON con la última descripción guardada en memoria."""
    return JSONResponse(content=ESTADO_ACTUAL)


@app.get("/latest-image")
def get_latest_image():
    """
    Obtiene la URL pública de la última foto desde Supabase Storage 
    y redirige el navegador automáticamente hacia ella.
    """
    try:
        # Pide la URL pública directo a Supabase
        res = supabase.storage.from_("fotos").get_public_url(NOMBRE_ARCHIVO_STORAGE)
        # Redirige a React directamente a la imagen de Supabase
        return RedirectResponse(url=res)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No se pudo obtener la imagen: {e}")


if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)