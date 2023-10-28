import os
from config import *
import telebot # para la api de telegram
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
import time # para los sleep
import requests
import json
import pickle
import re
import sys

# Comprobación inicial de variables
if "abc" == TELEGRAM_TOKEN:
    print("Se necesita configurar el token del bot con la variable TELEGRAM_TOKEN")
    sys.exit(1)

if 999 == TELEGRAM_ADMIN:
    print("Se necesita configurar el chatID del administrador con la variable TELEGRAM_ADMIN")
    sys.exit(1)

if 999 == TELEGRAM_INTERNAL_CHAT:
    TELEGRAM_INTERNAL_CHAT = TELEGRAM_ADMIN

if "abc" == SERVER_NAME:
    msg = "Se necesita cambiar el nombre del servidor con la variable SERVER_NAME"
    print(msg)
    sys.exit(1)

if "abc" == NOMBRE_CANAL_NOVEDADES:
    NOMBRE_CANAL_NOVEDADES = f'Novedades en {SERVER_NAME}'

if "imdb" != SEARCH_ENGINE and "filmaffinity" != SEARCH_ENGINE:
    msg = "El valor SEARCH_ENGINE de buscador ha de definirse, los valores son imdb o filmaffinity"
    print(msg)
    sys.exit(1)

if "HOST:PORT" == HOST_FILMAFFINITY_API:
    msg = "El valor HOST_FILMAFFINITY_API de buscador ha de definirse, la API puede consultarse en https://hub.docker.com/r/dgongut/filmaffinity-api"
    print(msg)
    sys.exit(1)

if "HOST:PORT" == HOST_IMDB_API:
    msg = "El valor HOST_IMDB_API de buscador ha de definirse, la API puede consultarse en https://hub.docker.com/r/dgongut/imdb-api"
    print(msg)
    sys.exit(1)

# Instanciamos el bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# CONSTANTES NO CONFIGURABLES
RESULTADOS_POR_FILA = 5
DELETE_TIME = 5
EDIT_TIME = 3

# SE CREA DICCIONARIO DE BUSQUEDAS
DIR = {"busquedas": "./busquedas/", "cache": "./cache/"}
for key in DIR:
    try:
        os.mkdir(DIR[key])
    except:
        pass

# Se crea la carpeta de peticiones si no existe ya
try:
    os.mkdir(os.path.basename(os.path.dirname(FICHERO_PETICIONES)))
except:
    pass

# Se crean los ficheros de peticiones si no existen ya
if not os.path.exists(FICHERO_PETICIONES):
    # Si no existe, crea el archivo vacío
    with open(FICHERO_PETICIONES, 'w') as archivo:
        pass

if not os.path.exists(FICHERO_PETICIONES_COMPLETADAS):
    # Si no existe, crea el archivo vacío
    with open(FICHERO_PETICIONES_COMPLETADAS, 'w') as archivo:
        pass

# Respondemos al comando /start
@bot.message_handler(commands=["start", "list", "busca"])
def command_controller(message):
    chatId = message.chat.id
    comando = message.text.split()[0]
    
    if comando in ('/start'):
        texto_inicial = ""
        if not is_admin(chatId):
            """Da la bienvenida al usuario"""
            texto_inicial = f'Bienvenido al bot de peticiones <b>{SERVER_NAME}</b>\n\n'
            texto_inicial += f'A continuación puedes compartir enlaces de <a href="https://www.filmaffinity.com/es/main.html">Filmaffinity</a> ó <a href="https://www.imdb.com">IMDb</a> para que se añadan a {SERVER_NAME}\n\n'
            texto_inicial += f'También puedes buscar directamente en {SEARCH_ENGINE} escribiendo lo siguiente:\n<code>/busca Gladiator</code>\n'
            texto_inicial += 'Serás avisado cuando se inicie su descarga'
        else:
            """Da la bienvenida al Administrador"""
            texto_inicial = f'Bienvenido al bot de peticiones <b>{SERVER_NAME}</b>\n\n'
            texto_inicial += 'A continuación puedes gestionar las peticiones de <a href="https://www.filmaffinity.com/es/main.html">Filmaffinity</a> y <a href="https://www.imdb.com">IMDb</a>\n\n'
            texto_inicial += 'Con el comando:\n<code>/list</code>\nPodrás marcar para <b>completar</b> o <b>borrar</b> las peticiones pendientes\n\n'
            texto_inicial += 'Cada una de estas acciones avisará al usuario'
        bot.send_message(chatId, texto_inicial, parse_mode="html", disable_web_page_preview=True)
       
    elif comando in ('/busca'):
        if is_admin(chatId):
            x = bot.send_message(chatId, "Esta función está dedicada para los usuarios, <b>no para el administrador.</b>", parse_mode="html")
            time.sleep(DELETE_TIME)
            bot.delete_message(chatId, message.message_id)
            bot.delete_message(chatId, x.message_id)
        else:
            textoBuscar = " ".join(message.text.split()[1:])
            if not textoBuscar: 
                # El usuario sólamente ha introducido /busca
                texto = 'Debes introducir algo en la búsqueda\n'
                texto += 'Ejemplo:\n'
                texto += f'<code>{message.text} Gladiator</code>\n\n'
                texto += '<b>Importante</b>: No incluyas el año en la búsqueda'
                bot.send_message(chatId, texto, parse_mode="html")
                return 1;
            
            else:
                if is_search_engine_filmaffinity():
                    elements = filmaffinity_search(textoBuscar)
                else:
                    elements = imdb_search(textoBuscar)
                if not elements:
                    bot.send_message(chatId, "❌ Lamentablemente, <b>no se han encontrado</b> resultados para el texto introducido\nRecuerda que <b>no debes</b> introducir el año en el texto de búsqueda", parse_mode="html")
                else:
                    display_page(elements, chatId)
    
    elif comando in ('/list'):
        """Comando lista"""
        if not is_admin(chatId):
            user_introduces_admin_command(message)
            return;

        bot.delete_message(chatId, message.message_id)
        
        if not peticiones_pendientes_empty(chatId):
            markup = InlineKeyboardMarkup(row_width = 3)
            textoMensaje = "<b>Completa</b> o <b>descarta</b> peticiones:\n"
            contador = 1
            botones = []

            with open(FICHERO_PETICIONES) as archivo:
                for linea in archivo:
                    lineaSplit = linea.split(sep='|')
                    textoMensaje += f'<b>[{str(contador)}]</b> {lineaSplit[1]} : {url_to_telegram_link(lineaSplit[2])} \n'
                    botones.append(InlineKeyboardButton(f'{str(contador)}: {extract_filmname_from_telegram_link(url_to_telegram_link(lineaSplit[2]))}', url=lineaSplit[2]))
                    botones.append(InlineKeyboardButton("✅", callback_data=lineaSplit[2]))
                    botones.append(InlineKeyboardButton("🗑️", callback_data=f'D|{lineaSplit[2]}'))
                    contador += 1
            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌ - Cerrar", callback_data="cerrar"))
            bot.send_message(chatId, textoMensaje, reply_markup=markup, disable_web_page_preview=True, parse_mode="html")
    
    elif not is_admin(chatId):
        """Un usuario normal ha introducido un comando"""
        text_controller(message)

@bot.message_handler(content_types=["text"])
def text_controller(message):
    """Gestiona los mensajes de texto, por aqui entrara el texto que deberan ser exclusivamente peticiones mediante un enlace directo"""
    chatId = message.chat.id
    name = f'<a href="tg://user?id={chatId}">{message.from_user.first_name}</a>'

    if message.text.startswith("/"):
        x = bot.send_message(chatId, "Comando no permitido, se reportará al administrador")
        bot.send_message(TELEGRAM_INTERNAL_CHAT, name + " ha enviado " + message.text)
        time.sleep(DELETE_TIME)
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)
    
    elif "filmaffinity.com" in message.text or "imdb.com" in message.text:
        if is_admin(chatId):
            x = bot.send_message(chatId, "El administrador no puede realizar peticiones")
            time.sleep(DELETE_TIME)
            bot.delete_message(chatId, message.message_id)
            bot.delete_message(chatId, x.message_id)
            return;

        # Buscar el primer enlace en el texto
        enlace = obtain_link_from_string(message.text)

        if enlace:
            enlaceEncontrado = enlace.group()
            add_peticion_with_messages(chatId, message.message_id, name, enlaceEncontrado)
        else:
            bot.send_message(chatId, "Enlace no válido.")
            bot.send_message(TELEGRAM_INTERNAL_CHAT, name + " ha enviado " + message.text)
        
    else:
        x = bot.send_message(chatId, "Este bot no es conversacional, el administrador <b>no recibirá</b> el mensaje si no va junto al enlace de Filmaffinity o IMDb\n\nProcedo a borrar los mensajes", parse_mode="html")
        time.sleep(DELETE_TIME)
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)

@bot.callback_query_handler(func=lambda mensaje: True)
def button_controller(call):
    """Se ha pulsado un boton"""
    chatId = call.from_user.id
    messageId = call.message.id
    name = f'<a href="tg://user?id={chatId}">{call.from_user.first_name}</a>'

    if call.data == "cerrar":
        bot.delete_message(chatId, messageId)
        delete_user_search(chatId, messageId)
        return

    if is_admin(chatId): # El admin solamente marca como completadas las peticiones, no puede pedir
        # Leer y filtrar las líneas
        with open(FICHERO_PETICIONES, 'r') as f:
            lines = f.readlines()

        if not is_peticion_deletable(call.data):
            # Marcamos petición como completada
            peticionesPendientes = []
            peticionCompletada = []
            name = ""
            previsualizeImage = ""

            for line in lines:
                if not line.endswith(call.data):
                    peticionesPendientes.append(line)
                else:
                    """Petición completada, avisamos al usuario"""
                    lineaSplit = line.split(sep='|')
                    userChatId = int(lineaSplit[0])
                    name = lineaSplit[1]
                    url = lineaSplit[2]
                    previsualizeImage = f'<a href="{read_cache_item_image(url)}"> </a>'
                    messageToUser = f'{previsualizeImage}{name}, tu petición: {url_to_telegram_link(url)}\n\n<b>Ha sido completada</b> ✅\n\nTardará unos minutos en aparecer, siempre podrás consultarlo en <i>{NOMBRE_CANAL_NOVEDADES}</i>\nGracias.'
                    bot.send_message(userChatId, str(messageToUser), parse_mode="html")
                    peticionCompletada.append(line)

            # Escribir las líneas filtradas
            with open(FICHERO_PETICIONES, 'w') as f:
                f.writelines(peticionesPendientes)

            # Agregar las líneas completadas al archivo de peticiones completadas
            with open(FICHERO_PETICIONES_COMPLETADAS, 'a') as f:
                f.writelines(peticionCompletada)

            bot.delete_message(chatId, messageId)
            bot.send_message(chatId, f'{previsualizeImage}La petición de {name} ha sido marcada como <b>completada</b> ✅', parse_mode="html")
        else:
            # Borramos la petición
            peticionesPendientes = []
            name = ""
            previsualizeImage = ""

            for line in lines:
                if not line.endswith(call.data[2:]): # con el [2:] le estamos quitando el D|
                    peticionesPendientes.append(line)
                else:
                    """Petición eliminada, avisamos al usuario"""
                    lineaSplit = line.split(sep='|')
                    userChatId = int(lineaSplit[0])
                    name = lineaSplit[1]
                    url = lineaSplit[2]
                    previsualizeImage = f'<a href="{read_cache_item_image(url)}"> </a>'
                    messageToUser = f"{previsualizeImage}{name}, tu petición: {url_to_telegram_link(url)}\n\nHa sido finalmente <b>eliminada</b> por el administrador ❌"
                    bot.send_message(userChatId, str(messageToUser), parse_mode="html")

            # Escribir las líneas filtradas
            with open(FICHERO_PETICIONES, 'w') as f:
                f.writelines(peticionesPendientes)

            bot.delete_message(chatId, messageId)
            bot.send_message(chatId, f'{previsualizeImage}La petición de {name} ha sido <b>eliminada</b> ✅', parse_mode="html")

    else: 
        """Gestiona las pulsaciones de los botones de paginación"""
        datos = get_user_search(chatId, messageId)
        
        if call.data == "anterior":
            if datos["pag"] == 0:
                bot.answer_callback_query(call.id, "Ya estás en la primera página")
            
            else:
                datos["pag"] -= 1
                set_user_search(chatId, messageId, datos)
                display_page(datos["lista"], chatId, datos["pag"], messageId)
            return
        
        elif call.data == "siguiente":
            if datos["pag"] * RESULTADOS_POR_PAGINA + RESULTADOS_POR_PAGINA >= len(datos["lista"]):
                bot.answer_callback_query(call.id, "Ya estás en la última página")
            
            else:
                datos["pag"] += 1
                set_user_search(chatId, messageId, datos)
                display_page(datos["lista"], chatId, datos["pag"], messageId)
            return
        
        else:
            # Ha pulsado en un resultado para hacer la petición
            add_peticion_with_messages(chatId, messageId, name, call.data)
            delete_user_search(chatId, messageId)

def display_page(lista, chatId, pag=0, messageId=None):
    """Crea o edita un mensaje de la página"""
    #Creamos la botonera
    markup = InlineKeyboardMarkup(row_width = RESULTADOS_POR_FILA)
    botonAnterior = InlineKeyboardButton("⬅", callback_data="anterior")
    botonCerrar = InlineKeyboardButton("❌", callback_data="cerrar")
    botonSiguiente = InlineKeyboardButton("➡", callback_data="siguiente")
    inicio = pag * RESULTADOS_POR_PAGINA # dónde empiezan los resultados (según la página)
    fin = inicio + RESULTADOS_POR_PAGINA
    
    if fin > len(lista):
        fin = len(lista)
    
    mensaje = f'<i>Resultados {inicio+1}-{fin} de {len(lista)}</i>\n'
    n = 1
    botones = []
    
    for item in lista[inicio:fin]:
        mensaje += f'[<b>{n}</b>] <a href="{item[1]}">{item[0]}</a>\n'
        botones.append(InlineKeyboardButton(str(n), callback_data=item[1]))
        n += 1
    
    markup.add(*botones)
    markup.row(botonAnterior, botonCerrar, botonSiguiente)
    
    if messageId:
        bot.edit_message_text(mensaje, chatId, messageId, reply_markup=markup, parse_mode="html", disable_web_page_preview=True)
    
    else:
        res = bot.send_message(chatId, mensaje, reply_markup=markup, parse_mode="html", disable_web_page_preview=True)
        messageId = res.message_id
        datos = {"pag":0, "lista":lista}
        set_user_search(chatId, messageId, datos)

def filmaffinity_search(searchText):
    urlSearch = f'{URL_BASE_API_FILMAFFINITY}/search?query={searchText.replace(" ", "%20")}'

    # Crear una lista para almacenar los títulos y URLs de las películas
    filmaffinityElements = []

    # Realizar una solicitud GET a la API
    response = requests.get(urlSearch)

    # Verificar si la solicitud fue exitosa (código de respuesta 200)
    if response.status_code == 200:
        data = response.json()

        for item in data:
            title = f"{item['title']} ({item['year']})"
            if item['rating'] != "--":
                title = f"{title} ({item['rating']}★)"
            url = item['url']
            write_cache_item(title, url, item["id"])
            write_cache_item_image(item['image'], item["id"])
            filmaffinityElements.append([title, url])

    elif response.status_code == 404:
        return filmaffinityElements
    else:
        # La solicitud no fue exitosa
        debug(f"Error al realizar la solicitud [{searchText}] a la API Filmaffinity. Código de respuesta:", response.status_code)
    
    return filmaffinityElements

def imdb_search(searchText):
    urlSearch = f'{URL_BASE_API_IMDB}/search?query={searchText.replace(" ", "%20")}'

    # Crear una lista para almacenar los títulos y URLs de las películas
    imdbElements = []

    # Realizar una solicitud GET a la API
    response = requests.get(urlSearch)

    # Verificar si la solicitud fue exitosa (código de respuesta 200)
    if response.status_code == 200:
        data = response.json()

        for item in data:
            url = item['url']
            title = f'{item["title"]} ({item["year"]})'
            write_cache_item(title, url, item["id"])
            imdbElements.append([title, url])

    elif response.status_code == 404:
        return imdbElements
    else:
        # La solicitud no fue exitosa
        debug(f"Error al realizar la solicitud [{searchText}] a la API IMDb. Código de respuesta:", response.status_code)
    
    return imdbElements

def url_to_telegram_link(url):
    try:
        return read_cache_item(url_to_film_code(url))
    except:
        specificUrl = None
        if is_filmaffinity_link(url):
            specificUrl = f'{URL_BASE_API_FILMAFFINITY}/film?url="{url}"'
        else:
            specificUrl = f'{URL_BASE_API_IMDB}/film?url="{url}"'
        specificData = requests.get(specificUrl).json()
        title = f"{specificData['title']} ({specificData['year']})"
        if specificData['rating'] != "--":
            title = f"{title} ({specificData['rating']}★)"
        write_cache_item(title, url, specificData['id'])
        write_cache_item_image(specificData['image'], specificData['id'])
        return get_telegram_link(title, url)

def url_to_film_code(url):
    numeroPelicula = None
    if is_filmaffinity_link(url):
        numeroPelicula = re.search(r'film(\d+)\.html', url)
    else:
        url = url.replace("\n", "")
        if not url.endswith("/"):
            url = f'{url}/'
        numeroPelicula = re.search(r'/tt(\d+)/', url)
    if numeroPelicula:
        numeroPelicula = numeroPelicula.group(1)
        return numeroPelicula
    else:
        raise ValueError(f'No se encontró un número de película en el enlace: {url}')

def get_telegram_link(title, url):
    return f'<a href="{url}">{title}</a>'

def write_cache_item(title, url, filmCode):
    pickle.dump(get_telegram_link(str(title).rstrip('\n'), str(url).rstrip('\n')), open(f'{DIR["cache"]}{filmCode}', 'wb'))

def read_cache_item(filmCode):
    return pickle.load(open(f'{DIR["cache"]}{filmCode}', 'rb'))

def write_cache_item_image(urlImage, filmCode):
    pickle.dump(urlImage.replace("mmed", "large"), open(f'{DIR["cache"]}{filmCode}_img', 'wb'))

def read_cache_item_image(url):
    try:
        return pickle.load(open(f'{DIR["cache"]}{url_to_film_code(url)}_img', 'rb'))
    except:
        return generate_image_cache(url)

def generate_image_cache(url):
    specificUrl = None
    if is_filmaffinity_link(url):
        specificUrl = f'{URL_BASE_API_FILMAFFINITY}/film?url="{url}"'
    else:
        specificUrl = f'{URL_BASE_API_IMDB}/film?url="{url}"'
    specificData = requests.get(specificUrl).json()
    write_cache_item_image(specificData['image'], url_to_film_code(url))
    return specificData['image']

def set_user_search(chatId, messageId, datos):
    pickle.dump(datos, open(f'{DIR["busquedas"]}{chatId}_{messageId}', 'wb'))

def get_user_search(chatId, messageId):
    return pickle.load(open(f'{DIR["busquedas"]}{chatId}_{messageId}', 'rb'))

def delete_user_search(chatId, messageId):
    os.remove(f'{DIR["busquedas"]}{chatId}_{messageId}')

def add_peticion_with_messages(chatId, messageId, name, url):
    linkTelegram = url_to_telegram_link(url)
    bot.delete_message(chatId, messageId) # borramos el mensaje de la petición
    previsualizeImage = f'<a href="{read_cache_item_image(url)}"> </a>'
    try:
        add_peticion(chatId, name, url)
        bot.send_message(chatId, f'{previsualizeImage}{name}, has solicitado con éxito:\n{linkTelegram}\nNotificado al administrador ✅', parse_mode="html")
        bot.send_message(TELEGRAM_INTERNAL_CHAT, f'{previsualizeImage}Nueva petición de {name}:\n{linkTelegram}', parse_mode="html")
        time.sleep(EDIT_TIME)
    except:
        bot.send_message(chatId, f'{previsualizeImage}{name}, la petición: {url_to_telegram_link(url)} ya se encuentra añadida y está en estado pendiente.', parse_mode="html")

def add_peticion(chatId, name, url):
    if check_if_exist_peticion(url):
        raise ValueError("Existe la peticion")
    archivo = open(FICHERO_PETICIONES, "a+")
    archivo.write(f"{chatId}|{name}|{url}\n")
    archivo.close()

def debug(message):
    bot.send_message(TELEGRAM_INTERNAL_CHAT, message, disable_web_page_preview=True)

def check_if_exist_peticion(url): 
    with open(FICHERO_PETICIONES, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if url_to_film_code(url) == url_to_film_code(obtain_link_from_string(line).group()):
                return True
    return False

def obtain_link_from_string(text):
    pattern = r"https?://[^\s]+"
    return re.search(pattern, text)

def is_peticion_deletable(peticion):
    # Las peticiones que están marcadas para borrar comienzan con D|
    return peticion.startswith('D|');

def is_admin(chatId):
    return chatId == TELEGRAM_ADMIN

def is_search_engine_filmaffinity():
    return SEARCH_ENGINE == "filmaffinity"

def is_filmaffinity_link(link):
    return "filmaffinity" in link

def user_introduces_admin_command(message):
    chatId = message.chat.id
    bot.delete_message(chatId, message.message_id)
    x = bot.send_message(chatId, f'El comando {message.text} está reservado al administrador', parse_mode="html", disable_web_page_preview=True)
    time.sleep(DELETE_TIME)
    bot.delete_message(chatId, x.message_id)

def peticiones_pendientes_empty(chatId):
    # Comprueba si hay peticiones pendientes. Si no las hay muestra un mensaje
    if os.path.getsize(FICHERO_PETICIONES) == 0:
        x = bot.send_message(chatId, "<b>No</b> hay peticiones disponibles ✅", parse_mode="html")
        time.sleep(DELETE_TIME)
        bot.delete_message(chatId, x.message_id)
        return True
    return False

def extract_filmname_from_telegram_link(telegram_link):
    result = re.search(r'>(.*?)</a>', telegram_link)
    if result:
        return result.group(1)
    else:
        return None

# MAIN
if __name__ == '__main__':
    print(f'Iniciando Bot de peticiones en {SERVER_NAME}')
    bot.set_my_commands([ # Comandos a mostrar en el menú de Telegram
        telebot.types.BotCommand("/start", "Da la bienvenida"),
        telebot.types.BotCommand("/busca", f'Busca en {SEARCH_ENGINE}'),
        telebot.types.BotCommand("/list",  "<ADMIN> Utilidad para completar o descartar peticiones")
        ])
    bot.infinity_polling() # Arranca la detección de nuevos comandos 
