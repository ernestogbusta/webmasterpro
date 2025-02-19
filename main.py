from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import requests

app = FastAPI()

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Obtener el token de Figma desde variables de entorno
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN")
FIGMA_FILE_KEY = "WnXRJb9D39JEVUir53ShUy"  # Cambia esto si el archivo en Figma cambia

# Modelo de respuesta esperada
class WireframeResponse(BaseModel):
    info: str
    download_url: str

# Verificación de API funcionando
@app.get("/")
def home():
    return {"message": "API funcionando correctamente en Render"}

# Endpoint para generar un wireframe con estilos de Figma
@app.post("/generate-wireframe", response_model=WireframeResponse)
async def generate_wireframe(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt")

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        # 🔍 1️⃣ Buscar un frame existente en Figma
        frame_id = find_existing_frame()

        if not frame_id:
            raise HTTPException(status_code=404, detail="No se encontró un frame existente en Figma")

        # 📥 2️⃣ Obtener la imagen del wireframe
        wireframe_url = get_figma_image(frame_id)

        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen de Figma")

        response_data = WireframeResponse(
            info="Wireframe generado correctamente",
            download_url=wireframe_url
        )

        return json.loads(response_data.json())

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# 🔍 **Función para encontrar un frame existente en Figma**
def find_existing_frame():
    try:
        headers = {"X-Figma-Token": FIGMA_TOKEN}
        url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes?ids=1527:615"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Error al obtener frame de Figma: {response.text}")
            return None

        data = response.json()
        node = data.get("nodes", {}).get("1527:615", {})

        return node.get("document", {}).get("id", None)

    except Exception as e:
        print(f"Error buscando frame en Figma: {e}")
        return None


# 📥 **Función para obtener la imagen del wireframe**
def get_figma_image(frame_id):
    try:
        headers = {"X-Figma-Token": FIGMA_TOKEN}
        url = f"https://api.figma.com/v1/images/{FIGMA_FILE_KEY}?ids={frame_id}"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Error al obtener imagen de Figma: {response.text}")
            return None

        image_data = response.json()
        return image_data.get("images", {}).get(frame_id, "")

    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None
