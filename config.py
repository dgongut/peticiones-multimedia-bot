import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ADMIN = int(os.environ.get("TELEGRAM_ADMIN"))
TELEGRAM_INTERNAL_CHAT = int(os.environ.get("TELEGRAM_INTERNAL_CHAT"))
SERVER_NAME = os.environ.get("SERVER_NAME")
NOMBRE_CANAL_NOVEDADES = os.environ.get("NOMBRE_CANAL_NOVEDADES")
RESULTADOS_POR_PAGINA = int(os.environ.get("RESULTADOS_POR_PAGINA"))
SEARCH_ENGINE = os.environ.get("SEARCH_ENGINE")
FICHERO_PETICIONES = "./peticiones/peticiones_pendientes.txt"
FICHERO_PETICIONES_COMPLETADAS = "./peticiones/peticiones_completadas.txt"
HOST_FILMAFFINITY_API = os.environ.get("HOST_FILMAFFINITY_API")
URL_BASE_API_FILMAFFINITY = f"http://{HOST_FILMAFFINITY_API}/api"
HOST_IMDB_API = os.environ.get("HOST_IMDB_API")
URL_BASE_API_IMDB = f"http://{HOST_IMDB_API}/api"