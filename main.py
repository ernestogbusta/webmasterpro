from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import json
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
    return "User-agent: *\nDisallow: /", 200, {"Content-Type": "text/plain"}


@app.post("/generate-wireframe", response_model=WireframeResponse)
async def generate_wireframe(request: Request):
    """
    Endpoint que genera un wireframe a partir de un prompt, buscando el mejor estilo en Figma
    y generando una imagen del wireframe resultante.
    """
    try:
        data = await request.json()
        prompt = data.get("prompt")
        format_type = data.get("format", "png")
        file_id = data.get("file_id", FIGMA_FILE_KEY)
        node_id = data.get("node_id")

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        # Obtener todos los node_id si no se especifica
        if not node_id:
            node_id_list = get_all_node_ids(file_id)
            if not node_id_list:
                raise HTTPException(status_code=400, detail="No se encontraron nodos en Figma")
            node_id = node_id_list[0]  # Usar el primer nodo disponible

        # Si el formato solicitado es "figma", devolver el node_id en lugar de la imagen
        if format_type == "figma":
            return WireframeResponse(info="Wireframe generado en Figma", download_url=f"https://www.figma.com/file/{file_id}?node-id={node_id}")

        # Obtener la imagen con URL reducida
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


def get_figma_image(file_id, node_id):
    """Obtiene la URL de la imagen de un nodo en Figma con escala reducida."""
    try:
        response = requests.get(
            f"https://api.figma.com/v1/images/{file_id}?ids={node_id}&scale=2",
            headers=HEADERS
        )
        if response.status_code == 200:
            img_url = response.json().get("images", {}).get(node_id, "")
            if not img_url:
                return None
            
            # Descargar la imagen y servirla desde el servidor
            local_filename = download_and_save_image(img_url)
            return f"https://webmasterpro.onrender.com/static/{local_filename}"

        else:
            print(f"Error al obtener imagen: {response.text}")
            return None
    except Exception as e:
        print(f"Error obteniendo imagen de Figma: {e}")
        return None


def download_and_save_image(image_url):
    """Descarga la imagen de Figma y la guarda localmente en /static/."""
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            filename = f"{uuid.uuid4()}.png"
            filepath = f"static/{filename}"

            os.makedirs("static", exist_ok=True)  # Crear directorio si no existe
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            return filename
        else:
            print(f"Error descargando imagen: {response.text}")
            return None
    except Exception as e:
        print(f"Error al descargar imagen: {e}")
        return None
