from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import time
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
FIGMA_FILE_KEY = "WnXRJb9D39JEVUir53ShUy"  # Debes cambiarlo si tu archivo en Figma cambia

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

        # 🔍 1️⃣ Seleccionar estilo adecuado según el prompt
        selected_style = get_best_matching_style(prompt)

        if not selected_style:
            raise HTTPException(status_code=400, detail="No se encontró un estilo adecuado en Figma")

        # 🎨 2️⃣ Crear un frame en Figma con el estilo elegido
        frame_id = create_frame_in_figma(selected_style)

        if not frame_id:
            raise HTTPException(status_code=500, detail="Error al crear el frame en Figma")

        # 📥 3️⃣ Obtener la imagen del wireframe
        wireframe_url = get_figma_image(frame_id)

        response_data = WireframeResponse(
            info="Wireframe generado correctamente con el estilo adecuado",
            download_url=wireframe_url
        )

        return json.loads(response_data.json())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# 🔍 **Función para encontrar el mejor estilo según el prompt**
def get_best_matching_style(prompt: str):
    try:
        # Descargar los estilos desde Figma
        headers = {"X-Figma-Token": FIGMA_TOKEN}
        url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/styles"

        response = requests.get(url, headers=headers)
        styles_data = response.json()

        # Buscar el estilo más adecuado
        best_match = None
        for style in styles_data.get("meta", {}).get("styles", []):
            style_name = style.get("name", "").lower()
            if any(keyword in prompt.lower() for keyword in style_name.split()):
                best_match = style
                break

        return best_match

    except Exception as e:
        print(f"Error obteniendo estilos: {e}")
        return None


# 🎨 **Función para crear un frame en Figma con un estilo específico**
def create_frame_in_figma(style):
    try:
        headers = {
            "X-Figma-Token": FIGMA_TOKEN,
            "Content-Type": "application/json"
        }

        frame_data = {
            "components": {
                "frame_1": {
                    "name": "Wireframe generado",
                    "type": "FRAME",
                    "absoluteBoundingBox": {"x": 100, "y": 100, "width": 600, "height": 400},
                    "style": {"backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1}},
                    "style_id": style["key"]  # Asigna el estilo elegido
                }
            }
        }

        url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}"
        response = requests.put(url, headers=headers, json=frame_data)

        if response.status_code == 200:
            return "frame_1"  # Devuelve el ID del frame
        else:
            print(f"Error al crear frame en Figma: {response.text}")
            return None

    except Exception as e:
        print(f"Error creando frame: {e}")
        return None


# 📥 **Función para obtener la imagen del wireframe**
def get_figma_image(frame_id):
    try:
        headers = {"X-Figma-Token": FIGMA_TOKEN}
        url = f"https://api.figma.com/v1/images/{FIGMA_FILE_KEY}?ids={frame_id}"

        response = requests.get(url, headers=headers)
        image_data = response.json()

        return image_data.get("images", {}).get(frame_id, "")

    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None
