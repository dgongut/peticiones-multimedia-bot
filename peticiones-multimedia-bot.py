import os
from config import *
import telebot # para la api de telegram
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
import time # para los sleep
import requests
from bs4 import BeautifulSoup
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
    print("Se necesita cambiar el nombre del servidor con la variable SERVER_NAME")
    sys.exit(1)

if "abc" == NOMBRE_CANAL_NOVEDADES:
    NOMBRE_CANAL_NOVEDADES = f'Novedades en {SERVER_NAME}'

if "imdb" != SEARCH_ENGINE and "filmaffinity" != SEARCH_ENGINE:
    print("El valor SEARCH_ENGINE de buscador ha de definirse, los valores son imdb o filmaffinity")
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
@bot.message_handler(commands=["start", "list", "busca", "borrar"])
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
            texto_inicial += 'Con el comando:\n<code>/list</code>\nPodrás marcar para <b>completar</b> las peticiones pendientes\n\n'
            texto_inicial += 'Con el comando:\n<code>/borrar</code>\nPodrás marcar para <b>borrar</b> las peticiones pendientes\n\n'
            texto_inicial += 'Cada una de estas acciones avisará al usuario'
        bot.delete_message(chatId, message.message_id)
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
                    url = f'{URL_BUSQUEDA_FILMAFFINITY}{textoBuscar.replace(" ", "%20")}'
                    headers = {"user-agent": USER_AGENT}
                    res = requests.get(url, headers=headers, timeout=10)
                    
                    if res.status_code != 200:
                        print(f'ERROR al buscar: {res.status_code} {res.reason}')
                        bot.send_message(chatId, "Se ha producido un error en la búsqueda\nInténtalo más tarde")
                        return 1;
                    
                    else:
                        # Búsqueda correcta, analizamos los resultados
                        elements = web_scrapping_filmaffinity_search_page(res.text)
                else:
                    url = f'{URL_BUSQUEDA_IMDB_BASE}{textoBuscar.replace(" ", "%20")}{URL_BUSQUEDA_IMDB_FINAL}'
                    headers = {"user-agent": USER_AGENT}
                    res = requests.get(url, headers=headers, timeout=10)
                    
                    if res.status_code != 200:
                        print(f'ERROR al buscar: {res.status_code} {res.reason}')
                        bot.send_message(chatId, "Se ha producido un error en la búsqueda\nInténtalo más tarde")
                        return 1;
                    
                    else:
                        # Búsqueda correcta, analizamos los resultados
                        elements = web_scrapping_imdb_search_page(res.text)

                if not elements:
                    # Cuando solo hay un resultado, no vamos a la pantalla de búsqueda sino a la página en sí de la película o serie, por lo que trataremos de obtener su información
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
            markup = InlineKeyboardMarkup(row_width = RESULTADOS_POR_FILA)
            textoMensaje = "Selecciona una petición para marcar como <b>completado</b>:\n"
            contador = 1
            botones = []

            with open(FICHERO_PETICIONES) as archivo:
                for linea in archivo:
                    lineaSplit = linea.split(sep='|')
                    textoMensaje += f'<b>[{str(contador)}]</b> {lineaSplit[1]} : {url_to_telegram_link(lineaSplit[2])} \n'
                    botones.append(InlineKeyboardButton(str(contador), callback_data=lineaSplit[2]))
                    contador += 1
            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌", callback_data="cerrar"))
            bot.send_message(chatId, textoMensaje, reply_markup=markup, disable_web_page_preview=True, parse_mode="html")

    elif comando in ('/borrar'):
        """Comando borrar petición"""
        if not is_admin(chatId):
            user_introduces_admin_command(message)
            return;

        bot.delete_message(chatId, message.message_id)
        
        if not peticiones_pendientes_empty(chatId):
            markup = InlineKeyboardMarkup(row_width = RESULTADOS_POR_FILA)
            textoMensaje = "Selecciona una petición para <b>borrarla</b>:\n"
            contador = 1
            botones = []

            with open(FICHERO_PETICIONES) as archivo:
                for linea in archivo:
                    lineaSplit = linea.split(sep='|')
                    textoMensaje += f'<b>[{str(contador)}]</b> {lineaSplit[1]} : {url_to_telegram_link(lineaSplit[2])} \n'
                    botones.append(InlineKeyboardButton(str(contador), callback_data=f'D|{lineaSplit[2]}'))
                    contador += 1
            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌", callback_data="cerrar"))
            bot.send_message(chatId, textoMensaje, reply_markup=markup, disable_web_page_preview=True, parse_mode="html")
    
    elif not is_admin(chatId):
        """Un usuario normal ha introducido un comando"""
        text_controller(message)

@bot.message_handler(content_types=["text"])
def text_controller(message):
    """Gestiona los mensajes de texto"""
    name = message.from_user.first_name
    chatId = message.chat.id
    
    if message.text.startswith("/"):
        x = bot.send_message(chatId, "Comando no permitido, se reportará al administrador")
        bot.send_message(TELEGRAM_INTERNAL_CHAT, name + " ha enviado " + message.text)
        time.sleep(DELETE_TIME)
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)
    
    elif "filmaffinity.com" in message.text or "imdb.com" in message.text:
        if is_admin(chatId):
            bot.send_message(chatId, "El administrador no puede realizar peticiones")
            return;

        # Patrón de expresión regular para encontrar enlaces
        pattern = r"https?://[^\s]+"

        # Buscar el primer enlace en el texto
        enlace = re.search(pattern, message.text)

        if enlace:
            enlaceEncontrado = enlace.group()
            # Chequeamos que devuelva un código de error correcto al menos
            headers = {"user-agent": USER_AGENT}
            res = requests.get(enlaceEncontrado, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f'ERROR al buscar: {res.status_code} {res.reason}')
                bot.send_message(chatId, f'Enlace no válido. {name} asegúrate de que el enlace que has enviado es correcto y lleva a una película o serie.')
                return 1;
            add_peticion_with_messages(chatId, message.message_id, message.from_user.first_name, enlaceEncontrado)
        else:
            bot.send_message(chatId, "Enlace no válido. No se permite el uso de acortadores de enlaces")
        
    else:
        x = bot.send_message(chatId, "Este bot no es conversacional, el administrador <b>no recibirá</b> el mensaje si no va junto al enlace de Filmaffinity\n\nProcedo a borrar los mensajes", parse_mode="html")
        time.sleep(DELETE_TIME)
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)

@bot.callback_query_handler(func=lambda mensaje: True)
def button_controller(call):
    """Gestiona el completado de una petición al presionar su botón (borra la linea del fichero y la añade a completadas)"""
    chatId = call.from_user.id
    messageId = call.message.id

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

            for line in lines:
                if not line.endswith(call.data):
                    peticionesPendientes.append(line)
                else:
                    """Petición completada, avisamos al usuario"""
                    lineaSplit = line.split(sep='|')
                    userChatId = int(lineaSplit[0])
                    name = lineaSplit[1]
                    url = lineaSplit[2]
                    messageToUser = f'{name}, tu petición: {url_to_telegram_link(url)}\n\n<b>Ha sido completada</b> ✅\n\nTardará unos minutos en aparecer, siempre podrás consultarlo en <i>{NOMBRE_CANAL_NOVEDADES}</i>\nGracias.'
                    bot.send_message(userChatId, str(messageToUser), parse_mode="html", disable_web_page_preview=True)
                    peticionCompletada.append(line)

            # Escribir las líneas filtradas
            with open(FICHERO_PETICIONES, 'w') as f:
                f.writelines(peticionesPendientes)

            # Agregar las líneas completadas al archivo de peticiones completadas
            with open(FICHERO_PETICIONES_COMPLETADAS, 'a') as f:
                f.writelines(peticionCompletada)

            bot.delete_message(chatId, messageId)
            bot.send_message(chatId, f'La petición de {name} ha sido marcada como completada ✅', parse_mode="html")
        else:
            # Borramos la petición
            peticionesPendientes = []
            name = ""

            for line in lines:
                if not line.endswith(call.data[2:]): # con el [2:] le estamos quitando el D|
                    peticionesPendientes.append(line)
                else:
                    """Petición eliminada, avisamos al usuario"""
                    lineaSplit = line.split(sep='|')
                    userChatId = int(lineaSplit[0])
                    name = lineaSplit[1]
                    url = lineaSplit[2]
                    messageToUser = f"{name}, tu petición: {url_to_telegram_link(url)}\n\nHa sido finalmente <b>eliminada</b> por el administrador ❌"
                    bot.send_message(userChatId, str(messageToUser), parse_mode="html", disable_web_page_preview=True)
                    

            # Escribir las líneas filtradas
            with open(FICHERO_PETICIONES, 'w') as f:
                f.writelines(peticionesPendientes)

            bot.delete_message(chatId, messageId)
            bot.send_message(chatId, f'La petición de {name} ha sido eliminada con éxito ✅', parse_mode="html")

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
            add_peticion_with_messages(chatId, messageId, call.from_user.first_name, call.data)
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

def web_scrapping_filmaffinity_search_page(htmlText):
    soup = BeautifulSoup(htmlText, "html.parser")
    # Encontrar todas las etiquetas con clase 'mc-title'
    filmaffinityRawElements = soup.find_all(class_='mc-title')

    # Crear una lista para almacenar los títulos y URLs de las películas
    filmaffinityElements = []

    # Comprobamos si no hay resultados
    noResults = soup.find('b', string=re.compile(r"No hay resultados?"))

    # Extraer títulos y URLs de las películas y agregar a la lista
    if noResults:
        return filmaffinityElements
    elif filmaffinityRawElements: # Hemos ido a la pantalla de búsqueda porque hay más de un resultado
        for title_element in filmaffinityRawElements:
            link = title_element.find('a')
            if link:
                title = link['title']
                url = link['href']

                # Encontrar el elemento 'ye-w' para el año de la película
                year_element = title_element.find_previous(class_='ye-w')
                year = year_element.get_text() if year_element else '-'

                # Encontrar la nota media de la película
                avg_rating_element = title_element.find_next(class_='avgrat-box')
                avg_rating = avg_rating_element.get_text() if avg_rating_element else '--'
                
                title = f'{title.strip()} ({year})'

                if avg_rating != '--':
                    title = f'{title} ({avg_rating}★)'

                write_cache_item(title, url)
                filmaffinityElements.append([title, url])
    else: # No hemos ido a la pantalla de búsqueda sino a la página de la película/serie en sí
        title = soup.title.text.rstrip(" - FilmAffinity")
        avg_rating = soup.find(id="movie-rat-avg")
        allLinks = soup.find_all('a')
        url = None
        for link in allLinks:
            if 'Ficha' in link.get_text():
                url = link['href']
                break
        if avg_rating:
           title = f'{title} ({avg_rating.get_text().strip()}★)'
        write_cache_item(title, url)
        filmaffinityElements.append([title, url])
    return filmaffinityElements

def web_scrapping_imdb_search_page(htmlText):
    soup = BeautifulSoup(htmlText, "html.parser")

    # Crear una lista para almacenar los títulos y URLs de las películas
    imdbElements = []

    imdbRawElements = soup.find_all('li', class_='ipc-metadata-list-summary-item')

    for title_element in imdbRawElements:
        # Extraer el nombre y el año
        title = title_element.find('a', class_='ipc-metadata-list-summary-item__t')
        if title:
            title = title.text
        else:
            continue
        year = title_element.find('span', class_='ipc-metadata-list-summary-item__li')
        if year:
            year = f' ({year.text.replace("– ", "")})' # Si es una serie que no ha terminado saldría por ejemplo (2020- )
        else:
            year = ""

        # Obtener la URL
        url_incomplete = title_element.find('a', class_='ipc-metadata-list-summary-item__t')['href']
        url = f"https://www.imdb.com{url_incomplete}"

        title = f'{title}{year}'
        write_cache_item(title, url)
        imdbElements.append([title, url])
    return imdbElements

def url_to_telegram_link(url):
    try:
        return read_cache_item(url_to_film_code(url))
    except:
        headers = {"user-agent": USER_AGENT}
        res = requests.get(str(url.rstrip("\n")), headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        if is_filmaffinity_link(url):
            title = soup.title.text.rstrip(" - FilmAffinity")
            avg_rating = soup.find(id="movie-rat-avg")
            if avg_rating:
               title = f'{title} ({avg_rating.get_text().strip()}★)'
            write_cache_item(title, url)
            return get_telegram_link(title, url)
        else:
            # Obtener el nombre de la película
            title = soup.title.text.rstrip(" - IMDb")
            write_cache_item(title, url)
            return get_telegram_link(title, url)
        
def url_to_film_code(url):
    numeroPelicula = ""
    if is_filmaffinity_link(url):
        numeroPelicula = re.search(r'film(\d+)\.html', url)
    else:
        numeroPelicula = re.search(r'/tt(\d+)/', url)

    if numeroPelicula:
        numeroPelicula = numeroPelicula.group(1)
        return numeroPelicula
    else:
        raise ValueError(f'No se encontró un número de película en el enlace: {url}')

def get_telegram_link(title, url):
    return f'<a href="{url}">{title}</a>'

def write_cache_item(title, url):
    pickle.dump(get_telegram_link(str(title).rstrip('\n'), str(url).rstrip('\n')), open(f'{DIR["cache"]}{url_to_film_code(url)}', 'wb'))

def read_cache_item(filmCode):
    return pickle.load(open(f'{DIR["cache"]}{filmCode}', 'rb'))

def set_user_search(chatId, messageId, datos):
    pickle.dump(datos, open(f'{DIR["busquedas"]}{chatId}_{messageId}', 'wb'))

def get_user_search(chatId, messageId):
    return pickle.load(open(f'{DIR["busquedas"]}{chatId}_{messageId}', 'rb'))

def delete_user_search(chatId, messageId):
    os.remove(f'{DIR["busquedas"]}{chatId}_{messageId}')

def add_peticion_with_messages(chatId, messageId, name, url):
    linkTelegram = url_to_telegram_link(url)
    bot.delete_message(chatId, messageId) # borramos el mensaje de la petición
    try:
        add_peticion(chatId, name, url)
        x = bot.send_message(chatId, f'Has solicitado con éxito: {linkTelegram}\nNotificando al administrador ⌚', parse_mode="html", disable_web_page_preview=True)
        bot.send_message(TELEGRAM_INTERNAL_CHAT, f'Nueva petición de {name}: {linkTelegram}', parse_mode="html", disable_web_page_preview=True)
        time.sleep(EDIT_TIME)
        bot.edit_message_text(f'Has solicitado con éxito: {linkTelegram}\nNotificado al administrador ✅', chatId, x.message_id, parse_mode="html", disable_web_page_preview=True)
    except:
        bot.send_message(chatId, f'{name}, la petición: {url_to_telegram_link(url)} ya se encontraba añadida.', parse_mode="html", disable_web_page_preview=True)

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
            if line.strip().endswith(url.strip()):
                return True
    return False

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

# MAIN
if __name__ == '__main__':
    print(f'Iniciando Bot de peticiones en {SERVER_NAME}')
    bot.set_my_commands([ # Comandos a mostrar en el menú de Telegram
        telebot.types.BotCommand("/start", "Da la bienvenida"),
        telebot.types.BotCommand("/busca", f'Busca en {SEARCH_ENGINE}'),
        telebot.types.BotCommand("/list",  "<ADMIN> Utilidad para completar peticiones"),
        telebot.types.BotCommand("/borrar","<ADMIN> Utilidad para descartar peticiones")
        ])
    bot.infinity_polling() # Arranca la detección de nuevos comandos 
