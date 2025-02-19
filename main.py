from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import json

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
    """
    Endpoint que genera un wireframe a partir de un prompt, buscando el mejor estilo en Figma
    y generando una imagen del wireframe resultante.
    """
    try:
        data = await request.json()
        prompt = data.get("prompt")
        file_id = data.get("file_id", FIGMA_FILE_KEY)
        node_id = data.get("node_id")

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        # Obtener todos los node_id si no se especifica
        if not node_id:
            node_id = get_all_node_ids(file_id)
            if not node_id:
                raise HTTPException(status_code=400, detail="No se encontraron nodos en Figma")

        selected_style = get_best_matching_style(prompt, file_id)
        if not selected_style:
            raise HTTPException(status_code=400, detail="No se encontró un estilo adecuado en Figma")

        # Figma NO permite la creación de nuevos nodos a través de la API
        # Por lo que esta parte se comenta y se sugiere hacer el wireframe manualmente
        # frame_id = create_frame_in_figma(selected_style, file_id, node_id)
        # if not frame_id:
        #     raise HTTPException(status_code=500, detail="Error al crear el frame en Figma")

        # En su lugar, obtenemos la imagen de un nodo existente
        wireframe_url = get_figma_image(file_id, node_id)
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        return WireframeResponse(info="Wireframe obtenido correctamente", download_url=wireframe_url)
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


def get_all_node_ids(file_id):
    """Obtiene todos los node_id dentro del archivo de Figma."""
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{file_id}", headers=HEADERS)
        if response.status_code != 200:
            print(f"Error obteniendo nodos: {response.text}")
            return None

        data = response.json()
        nodes = []

        def extract_nodes(node):
            if "id" in node:
                nodes.append(node["id"])
            if "children" in node:
                for child in node["children"]:
                    extract_nodes(child)

        extract_nodes(data.get("document", {}))
        return nodes if nodes else None

    except Exception as e:
        print(f"Error al obtener los nodos de Figma: {e}")
        return None


def get_best_matching_style(prompt: str, file_id):
    """Busca el mejor estilo en Figma basado en el prompt."""
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{file_id}/styles", headers=HEADERS)
        if response.status_code != 200:
            print(f"Error obteniendo estilos: {response.text}")
            return None

        styles = response.json().get("meta", {}).get("styles", [])
        
        if not styles:
            print("No se encontraron estilos en Figma.")
            return None

        prompt_lower = prompt.lower()

        for style in styles:
            if any(keyword in prompt_lower for keyword in style.get("name", "").lower().split()):
                return style

        return styles[0] if styles else None
    except Exception as e:
        print(f"Error obteniendo estilos: {e}")
        return None


def get_figma_image(file_id, node_id):
    """Obtiene la URL de la imagen de un nodo en Figma."""
    try:
        response = requests.get(f"https://api.figma.com/v1/images/{file_id}?ids={node_id}", headers=HEADERS)
        if response.status_code == 200:
            return response.json().get("images", {}).get(node_id, "")
        else:
            print(f"Error al obtener imagen: {response.text}")
            return None
    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None
