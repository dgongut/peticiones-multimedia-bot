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
URL_BUSQUEDA_FILMAFFINITY = "https://www.filmaffinity.com/es/search.php?stype=title&stext="
URL_BUSQUEDA_IMDB_BASE = "https://www.imdb.com/find/?s=tt&q="
URL_BUSQUEDA_IMDB_FINAL = "&ref_=nv_sr_sm"
USER_AGENT = "Mozilla/5.0 (iPad; CPU OS 14_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"