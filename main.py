from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import requests
import uuid
import logging
import gc  # 🔹 Garbage Collector para liberar memoria

# 📌 Configuración del logger
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")
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
    """Genera un wireframe a partir de un prompt usando Figma."""
    try:
        if request:
            data = await request.json()
            prompt = data.get("prompt", prompt)

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        file_id = FIGMA_FILE_KEY

        # ✅ 1️⃣ Obtener nodos relevantes (máximo 3 nodos)
        nodes = get_relevant_nodes(file_id, prompt)
        if not nodes:
            raise HTTPException(status_code=400, detail="No se encontraron nodos relevantes en Figma")

        valid_nodes = nodes[:3]  # 🔹 Limitamos a 3 nodos para reducir errores
        if not valid_nodes:
            raise HTTPException(status_code=500, detail="Nodos inválidos o vacíos")

        # ✅ 2️⃣ Seleccionar UN SOLO nodo renderizable para evitar errores
        selected_node_id = select_renderable_node(valid_nodes)
        if not selected_node_id:
            raise HTTPException(status_code=500, detail="No se pudo seleccionar un nodo válido")

        # ✅ 3️⃣ Obtener la imagen desde Figma
        wireframe_url = get_figma_image(file_id, selected_node_id)
        if not wireframe_url:
            logger.warning(f"⚠️ No se pudo obtener la imagen para el nodo {selected_node_id}")
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        # ✅ 4️⃣ Descargar y guardar la imagen localmente
        local_filename = download_and_save_image(wireframe_url)
        if not local_filename:
            raise HTTPException(status_code=500, detail="Error al guardar la imagen")

        # ✅ 5️⃣ Liberar memoria manualmente
        gc.collect()  # 🔹 Garbage Collector

        return WireframeResponse(
            info="Wireframe generado correctamente",
            download_url=f"https://webmasterpro.onrender.com/static/{local_filename}"
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"❌ Error interno: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


def get_relevant_nodes(file_id, prompt):
    """Filtra y selecciona un máximo de 5 nodos relevantes según el prompt."""
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{file_id}", headers=HEADERS)
        if response.status_code != 200:
            logger.error(f"⚠️ Error al obtener nodos: {response.status_code}")
            return None

        data = response.json()
        nodes = []

        def extract_nodes(node):
            if "id" in node and node.get("type") in ["FRAME", "COMPONENT", "RECTANGLE", "VECTOR"]:
                nodes.append(node["id"])
            if "children" in node:
                for child in node["children"]:
                    extract_nodes(child)

        extract_nodes(data.get("document", {}))

        return nodes[:5] if nodes else None  # 🔹 Limitamos a 5 nodos máximo
    except Exception as e:
        logger.error(f"❌ Error al obtener nodos de Figma: {e}")
        return None


def select_renderable_node(nodes):
    """Selecciona un nodo que Figma pueda renderizar como imagen."""
    for node in nodes:
        if node:  # 🔹 Asegurarse de que el nodo no sea None o inválido
            return node
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
            logger.error(f"⚠️ Error al obtener imagen: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Error obteniendo imagen de Figma: {e}")
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
            logger.error(f"⚠️ Error descargando imagen: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Error al descargar imagen: {e}")
        return None
