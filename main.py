from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import shutil
import uuid

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

@app.get("/robots.txt")
def robots():
    return "User-agent: *\nDisallow:", 200

@app.post("/generate-wireframe", response_model=WireframeResponse)
async def generate_wireframe(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt")
        file_id = data.get("file_id", FIGMA_FILE_KEY)
        node_id = data.get("node_id")

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        if not node_id:
            node_id = get_all_node_ids(file_id)
            if not node_id:
                raise HTTPException(status_code=400, detail="No se encontraron nodos en Figma")

        selected_style = get_best_matching_style(prompt, file_id)
        if not selected_style:
            raise HTTPException(status_code=400, detail="No se encontró un estilo adecuado en Figma")

        wireframe_url = get_figma_image(file_id, node_id)
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="Error al obtener la imagen de Figma (puede ser una URL demasiado larga)")
        
        download_url = download_and_serve_figma_image(wireframe_url)
        if not download_url:
            raise HTTPException(status_code=500, detail="Error al descargar y servir la imagen")

        return WireframeResponse(info="Wireframe obtenido correctamente", download_url=download_url)
    
    except HTTPException as http_exc:
        print(f"HTTPException: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        print(f"Error inesperado: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

def get_all_node_ids(file_id):
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

def download_and_serve_figma_image(figma_url):
    try:
        response = requests.get(figma_url, stream=True)
        if response.status_code != 200:
            print(f"Error descargando imagen: {response.text}")
            return None

        file_name = f"static/{uuid.uuid4()}.png"
        os.makedirs("static", exist_ok=True)
        with open(file_name, "wb") as out_file:
            shutil.copyfileobj(response.raw, out_file)

        return f"https://webmasterpro.onrender.com/{file_name}"
    except Exception as e:
        print(f"Error guardando imagen: {e}")
        return None
