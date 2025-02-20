from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import requests
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

        # ✅ 1️⃣ Obtener una lista de nodos disponibles
        node_id_list = get_all_node_ids(file_id)

        if not node_id_list:
            raise HTTPException(status_code=400, detail="No se encontraron nodos en Figma")

        # ⚠️ Evitar seleccionar `0:0` (probablemente sea un fondo vacío)
        node_id_list = [n for n in node_id_list if n != "0:0"]

        if not node_id_list:
            raise HTTPException(status_code=400, detail="No hay nodos válidos en el archivo de Figma")

        # ✅ 2️⃣ Seleccionar el primer nodo con contenido
        node_id = node_id_list[0]
        print(f"✅ Nodo seleccionado: {node_id}")

        # ✅ 3️⃣ Obtener la imagen con la URL correcta
        wireframe_url = get_figma_image(file_id, node_id)
        if not wireframe_url:
            raise HTTPException(status_code=500, detail="No se pudo obtener la imagen del wireframe")

        # ✅ 4️⃣ Guardar la imagen localmente en /static/
        local_filename = download_and_save_image(wireframe_url)
        if not local_filename:
            raise HTTPException(status_code=500, detail="Error al guardar la imagen")

        return WireframeResponse(info="Wireframe obtenido correctamente", download_url=f"https://webmasterpro.onrender.com/static/{local_filename}")
    
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
        print(f"📌 Lista de nodos obtenida: {nodes}")
        return nodes if nodes else None

    except Exception as e:
        print(f"Error al obtener los nodos de Figma: {e}")
        return None


def get_figma_image(file_id, node_id):
    """Obtiene la URL de la imagen de un nodo en Figma con escala mejorada."""
    try:
        print(f"🔍 Solicitando imagen para file_id={file_id} y node_id={node_id}")

        response = requests.get(
            f"https://api.figma.com/v1/images/{file_id}?ids={node_id}&scale=3&format=png",
            headers=HEADERS
        )

        if response.status_code == 200:
            img_url = response.json().get("images", {}).get(node_id, "")
            if not img_url:
                print("⚠️ La API de Figma no devolvió una URL de imagen.")
                return None
            print(f"✅ URL de imagen obtenida: {img_url}")
            return img_url
        else:
            print(f"❌ Error al obtener imagen: {response.text}")
            return None

    except Exception as e:
        print(f"⚠️ Error obteniendo imagen de Figma: {e}")
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

            print(f"✅ Imagen guardada en {filepath}")
            return filename
        else:
            print(f"Error descargando imagen: {response.text}")
            return None
    except Exception as e:
        print(f"Error al descargar imagen: {e}")
        return None
