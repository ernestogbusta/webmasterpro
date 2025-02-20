from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import requests
import uuid
import logging

# 📌 Configuración del logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# 📌 Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📌 Crear directorio `static/` si no existe
STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)

# 📌 Montar la carpeta `static/` para servir imágenes
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 📌 Configuración de la API de Figma
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN")
FIGMA_FILE_KEY = "WnXRJb9D39JEVUir53ShUy"
HEADERS = {"X-Figma-Token": FIGMA_TOKEN, "Content-Type": "application/json"}

# 📌 Modelo de respuesta esperada
class WireframeResponse(BaseModel):
    info: str
    download_url: str

@app.get("/generate-wireframe", response_model=WireframeResponse)
@app.post("/generate-wireframe", response_model=WireframeResponse)
async def generate_wireframe(request: Request = None, prompt: str = Query(None)):
    """Genera un wireframe basado en un prompt, combinando y reorganizando elementos de Figma."""
    try:
        if request:
            data = await request.json()
            prompt = data.get("prompt", prompt)
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        file_id = FIGMA_FILE_KEY

        # ✅ 1️⃣ Obtener nodos relevantes según el prompt
        nodes = get_relevant_nodes(file_id, prompt)
        
        if not nodes:
            raise HTTPException(status_code=400, detail="No se encontraron nodos relevantes en Figma")

        # ✅ 2️⃣ Generar una composición nueva en un frame
        new_frame_id = create_new_frame(file_id, nodes)
        
        if not new_frame_id:
            raise HTTPException(status_code=500, detail="No se pudo generar un frame válido")

        # ✅ 3️⃣ Obtener la imagen del frame creado
        wireframe_url = get_figma_image(file_id, new_frame_id)
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        # ✅ 4️⃣ Guardar la imagen localmente en /static/
        local_filename = download_and_save_image(wireframe_url)
        if not local_filename:
            raise HTTPException(status_code=500, detail="Error al guardar la imagen")

        return WireframeResponse(info="Wireframe generado correctamente", download_url=f"https://webmasterpro.onrender.com/static/{local_filename}")
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


def get_relevant_nodes(file_id, prompt):
    """Filtra y selecciona nodos relevantes según el prompt."""
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{file_id}", headers=HEADERS)
        if response.status_code != 200:
            logger.error(f"Error obteniendo nodos: {response.text}")
            return None

        data = response.json()
        nodes = []

        def extract_nodes(node):
            if "id" in node and node.get("type") in ["FRAME", "COMPONENT"]:
                nodes.append(node["id"])
            if "children" in node:
                for child in node["children"]:
                    extract_nodes(child)

        extract_nodes(data.get("document", {}))
        
        return nodes[:3] if nodes else None  # Elegimos hasta 3 nodos
    except Exception as e:
        logger.exception(f"Error al obtener nodos de Figma: {e}")
        return None


def create_new_frame(file_id, nodes):
    """Crea un nuevo frame en Figma con los nodos seleccionados y aplica estilos básicos."""
    try:
        url = f"https://api.figma.com/v1/files/{file_id}/frames"
        data = {
            "name": "Nuevo Wireframe",
            "type": "FRAME",
            "children": nodes,  # Añadimos los nodos al nuevo frame
            "backgroundColor": "#FFFFFF",
            "size": {"width": 800, "height": 600}
        }

        response = requests.post(url, headers=HEADERS, json=data)
        
        if response.status_code == 200:
            frame_id = response.json().get("id")
            return frame_id
        else:
            logger.error(f"Error creando frame en Figma: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Error al crear frame en Figma: {e}")
        return None


def get_figma_image(file_id, node_id):
    """Obtiene la URL de la imagen de un nodo en Figma."""
    try:
        response = requests.get(
            f"https://api.figma.com/v1/images/{file_id}?ids={node_id}&scale=3&format=png",
            headers=HEADERS
        )
        if response.status_code == 200:
            return response.json().get("images", {}).get(node_id, "")
        else:
            logger.error(f"Error al obtener imagen: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Error obteniendo imagen de Figma: {e}")
        return None


def download_and_save_image(image_url):
    """Descarga la imagen y la guarda en /static/."""
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            filename = f"{uuid.uuid4()}.png"
            filepath = os.path.join(STATIC_DIR, filename)
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return filename
        else:
            logger.error(f"Error descargando imagen: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Error al descargar imagen: {e}")
        return None


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
