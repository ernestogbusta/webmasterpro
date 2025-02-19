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

# Configuración de la API de Figma
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN")
FIGMA_FILE_KEY = "WnXRJb9D39JEVUir53ShUy"
HEADERS = {"X-Figma-Token": FIGMA_TOKEN, "Content-Type": "application/json"}

# Modelo de respuesta esperada
class WireframeResponse(BaseModel):
    info: str
    download_url: str

@app.get("/")
def home():
    return {"message": "API funcionando correctamente"}

@app.post("/generate-wireframe", response_model=WireframeResponse)
async def generate_wireframe(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt")
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")
        
        selected_style = get_best_matching_style(prompt)
        if not selected_style:
            raise HTTPException(status_code=400, detail="No se encontró un estilo adecuado en Figma")

        frame_id = create_frame_in_figma(selected_style)
        if not frame_id:
            raise HTTPException(status_code=500, detail="Error al crear el frame en Figma")

        wireframe_url = get_figma_image(frame_id)
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        return WireframeResponse(info="Wireframe generado correctamente", download_url=wireframe_url)
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


def get_best_matching_style(prompt: str):
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/styles", headers=HEADERS)
        if response.status_code != 200:
            return None
        
        styles = response.json().get("meta", {}).get("styles", [])
        
        prompt_lower = prompt.lower()
        for style in styles:
            if any(keyword in prompt_lower for keyword in style.get("name", "").lower().split()):
                return style
        
        return styles[0] if styles else None
    except Exception as e:
        print(f"Error obteniendo estilos: {e}")
        return None


def create_frame_in_figma(style):
    try:
        frame_data = {
            "name": "Wireframe generado",
            "type": "FRAME",
            "absoluteBoundingBox": {"x": 100, "y": 100, "width": 800, "height": 600},
            "style": {"backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1}},
            "style_id": style["key"]
        }
        
        response = requests.post(f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes", headers=HEADERS, json=frame_data)
        if response.status_code == 200:
            return response.json().get("id", "")
        else:
            print(f"Error al crear frame en Figma: {response.text}")
            return None
    except Exception as e:
        print(f"Error creando frame: {e}")
        return None


def get_figma_image(frame_id):
    try:
        response = requests.get(f"https://api.figma.com/v1/images/{FIGMA_FILE_KEY}?ids={frame_id}", headers=HEADERS)
        if response.status_code == 200:
            return response.json().get("images", {}).get(frame_id, "")
        else:
            print(f"Error al obtener imagen: {response.text}")
            return None
    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None
