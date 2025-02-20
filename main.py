from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import requests
import uuid
import logging
import random

# Configuración del logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Habilitar CORS
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

# 🔥 Montar la carpeta `static/` para servir imágenes
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
    Genera un wireframe a partir de un prompt, seleccionando y reorganizando los mejores nodos de Figma.
    """
    try:
        data = await request.json()
        prompt = data.get("prompt")
        file_id = data.get("file_id", FIGMA_FILE_KEY)

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt no recibido")

        # ✅ 1️⃣ Obtener nodos relevantes según el prompt
        node_id_list = get_filtered_nodes(file_id, prompt)

        if not node_id_list:
            raise HTTPException(status_code=400, detail="No se encontraron nodos válidos en Figma")

        # ✅ 2️⃣ Reordenar creativamente los nodos seleccionados
        ordered_nodes = reorder_nodes_creatively(node_id_list)

        # ✅ 3️⃣ Obtener la imagen del wireframe
        wireframe_url = get_figma_image(file_id, ordered_nodes[0])
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        # ✅ 4️⃣ Guardar la imagen localmente
        local_filename = download_and_save_image(wireframe_url)
        if not local_filename:
            raise HTTPException(status_code=500, detail="Error al guardar la imagen")

        return WireframeResponse(info="Wireframe generado exitosamente", 
                                 download_url=f"https://webmasterpro.onrender.com/static/{local_filename}")
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


def get_filtered_nodes(file_id, prompt):
    """Filtra nodos en Figma según el prompt."""
    try:
        response = requests.get(f"https://api.figma.com/v1/files/{file_id}", headers=HEADERS)
        if response.status_code != 200:
            logger.error(f"Error obteniendo nodos: {response.text}")
            return None

        data = response.json()
        nodes = []

        def extract_nodes(node):
            """Extrae nodos relevantes según el tipo."""
            if "id" in node and node.get("type") in ["FRAME", "COMPONENT"] and node.get("id") != "0:0":
                nodes.append((node["id"], node.get("absoluteBoundingBox", {}).get("width", 0)))

            if "children" in node:
                for child in node["children"]:
                    extract_nodes(child)

        extract_nodes(data.get("document", {}))

        if not nodes:
            logger.warning("⚠️ No se encontraron nodos adecuados.")
            return None

        # Filtrar nodos que contengan palabras clave del prompt
        filtered_nodes = [n[0] for n in nodes if any(word.lower() in prompt.lower() for word in ["header", "footer", "button", "card"])]

        if not filtered_nodes:
            filtered_nodes = [n[0] for n in nodes]  # Si no hay coincidencias, usar todos

        logger.info(f"📌 {len(filtered_nodes)} nodos filtrados para el prompt: {prompt}")
        return filtered_nodes

    except Exception as e:
        logger.exception(f"Error al obtener los nodos de Figma: {e}")
        return None


def reorder_nodes_creatively(node_list):
    """Reorganiza los nodos de manera aleatoria y creativa para generar wireframes únicos."""
    random.shuffle(node_list)  # Desordenar aleatoriamente los nodos
    return node_list[:5]  # Tomar hasta 5 nodos para componer el wireframe


def get_figma_image(file_id, node_id):
    """Obtiene la URL de la imagen de un nodo en Figma con escala mejorada."""
    try:
        logger.info(f"🔍 Solicitando imagen para file_id={file_id} y node_id={node_id}")

        response = requests.get(
            f"https://api.figma.com/v1/images/{file_id}?ids={node_id}&scale=3&format=png",
            headers=HEADERS
        )

        if response.status_code == 200:
            img_url = response.json().get("images", {}).get(node_id, "")
            if not img_url:
                logger.warning("⚠️ La API de Figma no devolvió una URL de imagen.")
                return None
            logger.info("✅ URL de imagen obtenida correctamente")
            return img_url
        else:
            logger.error(f"❌ Error al obtener imagen: {response.text}")
            return None

    except Exception as e:
        logger.exception(f"⚠️ Error obteniendo imagen de Figma: {e}")
        return None


def download_and_save_image(image_url):
    """Descarga la imagen de Figma y la guarda localmente en /static/."""
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            filename = f"{uuid.uuid4()}.png"
            filepath = os.path.join(STATIC_DIR, filename)

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            logger.info(f"✅ Imagen guardada en {filepath}")
            return filename
        else:
            logger.error(f"Error descargando imagen: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Error al descargar imagen: {e}")
        return None
