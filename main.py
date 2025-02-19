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

        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen de Figma")

        response_data = WireframeResponse(
            info="Wireframe generado correctamente con el estilo adecuado",
            download_url=wireframe_url
        )

        return json.loads(response_data.json())

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# 🔍 **Función para encontrar el mejor estilo según el prompt**
def get_best_matching_style(prompt: str):
    try:
        headers = {"X-Figma-Token": FIGMA_TOKEN}
        url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/styles"

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Error al obtener estilos de Figma: {response.text}")
            return None

        styles_data = response.json()

        available_styles = styles_data.get("meta", {}).get("styles", [])

        if not available_styles:
            print("No se encontraron estilos en Figma.")
            return None

        prompt_lower = prompt.lower()

        # Buscar coincidencia exacta
        for style in available_styles:
            style_name = style.get("name", "").lower()
            if any(keyword in prompt_lower for keyword in style_name.split()):
                return style

        # Si no hay coincidencias exactas, devolver el primer estilo disponible como fallback
        return available_styles[0] if available_styles else None

    except Exception as e:
        print(f"Error obteniendo estilos de Figma: {e}")
        return None


# 🎨 **Función para crear un frame en Figma con un estilo específico**
def create_frame_in_figma(style):
    try:
        headers = {
            "X-Figma-Token": FIGMA_TOKEN,
            "Content-Type": "application/json"
        }

        frame_data = {
            "name": "Wireframe generado",
            "type": "FRAME",
            "absoluteBoundingBox": {"x": 100, "y": 100, "width": 600, "height": 400},
            "style": {"backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1}},
            "style_id": style["key"]
        }

        url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes"

        response = requests.post(url, headers=headers, json=frame_data)

        if response.status_code == 200:
            response_json = response.json()
            node_id = response_json.get("id", "")
            return node_id if node_id else None
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

        if response.status_code != 200:
            print(f"Error al obtener imagen de Figma: {response.text}")
            return None

        image_data = response.json()
        return image_data.get("images", {}).get(frame_id, "")

    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None
