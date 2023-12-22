import os
from config import *
import telebot
import mysql.connector
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
import time
import requests
import json
import re
import sys

VERSION = "3.1.0"

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

if "HOST:PORT" == DATABASE_HOST:
    msg = "El valor DATABASE_HOST ha de definirse"
    print(msg)
    sys.exit(1)

if "abc" == DATABASE_PASSWORD:
    msg = "El valor DATABASE_PASSWORD ha de definirse"
    print(msg)
    sys.exit(1)

if "abc" == DATABASE_NAME:
    msg = "El valor DATABASE_NAME ha de definirse"
    print(msg)
    sys.exit(1)

if "abc" == DATABASE_USER:
    msg = "El valor DATABASE_USER ha de definirse"
    print(msg)
    sys.exit(1)

# Instanciamos el bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# CONSTANTES NO CONFIGURABLES
BASIC_CONFIG = {
    'RESULTADOS_POR_FILA': 5,
    'DELETE_TIME': 5,
    'EDIT_TIME': 3,
}
STATUS = {
    'PENDIENTE': 0,
    'COMPLETADA': 1,
    'DENEGADA': 2,
}
WEBPAGE = {
    'FILMAFFINITY': 0,
    'IMDB': 1,
}


# =======================================================================
# =======================================================================
#   _____ ____  _   _ _______ _____   ____  _      _      ______ _____  
#  / ____/ __ \| \ | |__   __|  __ \ / __ \| |    | |    |  ____|  __ \ 
# | |   | |  | |  \| |  | |  | |__) | |  | | |    | |    | |__  | |__) |
# | |   | |  | | . ` |  | |  |  _  /| |  | | |    | |    |  __| |  _  / 
# | |___| |__| | |\  |  | |  | | \ \| |__| | |____| |____| |____| | \ \ 
#  \_____\____/|_| \_|  |_|  |_|  \_\\____/|______|______|______|_|  \_\                                                                      
#
# =======================================================================
# =======================================================================

# Respondemos a los comandos /XXXX
@bot.message_handler(commands=["start", "list", "busca", "ban", "unban", "send", "sendtouser", "version"])
def command_controller(message):
    chatId = message.chat.id
    comando = message.text.split()[0]
    update_user(message)
    if not is_user_allowed(chatId):
        bot.send_message(chatId, "Lamentablemente, <b>has sido baneado del bot.</b>", parse_mode="html")
        return

    if comando in ('/start'):
        texto_inicial = ""
        if not is_admin(chatId):
            """Da la bienvenida al usuario"""
            texto_inicial = f'Bienvenido al bot de peticiones <b>{SERVER_NAME}</b>\n\n'
            texto_inicial += f'A continuación puedes compartir enlaces de <a href="https://www.filmaffinity.com/es/main.html">Filmaffinity</a> ó <a href="https://www.imdb.com">IMDb</a> para que se añadan a {SERVER_NAME}\n\n'
            texto_inicial += f'También puedes buscar directamente en {SEARCH_ENGINE} escribiendo lo siguiente:\n<code>/busca Gladiator</code>\n'
            texto_inicial += 'Con el comando:\n<code>/list</code>\nPodrás <b>borrar</b> tus peticiones pendientes\n\n'
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
            time.sleep(BASIC_CONFIG['DELETE_TIME'])
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
        bot.delete_message(chatId, message.message_id)
        if is_admin(chatId):
            markup = InlineKeyboardMarkup(row_width = 3)
            textoMensaje = "<b>Completa</b> o <b>descarta</b> peticiones:\n"
            contador = 1
            botones = []

            query = """
                    SELECT p.film_code, p.webpage_id, u.name, u.chat_id
                    FROM peticiones p
                    JOIN usuarios u ON p.chat_id = u.chat_id
                    WHERE p.status_id = %s;
            """

            resultados = executeQuery(query, (STATUS['PENDIENTE'],))

            if len(resultados) == 0:
                x = bot.send_message(chatId, "<b>No</b> hay peticiones pendientes ✅", parse_mode="html")
                time.sleep(BASIC_CONFIG['DELETE_TIME'])
                bot.delete_message(chatId, x.message_id)
                return

            # Iterar sobre los resultados e imprimir la información
            for resultado in resultados:
                film_code, webpage, name, userId = resultado
                url = film_code_to_url(film_code, webpage)
                telegram_link = url_to_telegram_link(url)
                name = telegram_name_with_link(userId, name)
                textoMensaje += f'<b>[{str(contador)}]</b> {name} : {telegram_link} \n'
                botones.append(InlineKeyboardButton(f'{str(contador)}: {extract_filmname_from_telegram_link(telegram_link)}', url=url))
                botones.append(InlineKeyboardButton("✅", callback_data=url))
                botones.append(InlineKeyboardButton("🗑️", callback_data=f'D|{url}'))
                contador += 1

            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌ - Cerrar", callback_data="cerrar"))
            bot.send_message(chatId, textoMensaje, reply_markup=markup, disable_web_page_preview=True, parse_mode="html")
        else:
            markup = InlineKeyboardMarkup(row_width = 1)
            textoMensaje = "<b>Descarta</b> tus peticiones haciendo clic en ellas.\n\nSi no quieres eliminar ninguna pulsa en <code>Cerrar</code>.\n"
            contador = 1
            botones = []

            query = """
                    SELECT p.film_code, p.webpage_id, u.name, u.chat_id
                    FROM peticiones p
                    JOIN usuarios u ON p.chat_id = u.chat_id
                    WHERE p.status_id = %s AND p.chat_id = %s;
            """

            resultados = executeQuery(query, (STATUS['PENDIENTE'], chatId))

            if len(resultados) == 0:
                x = bot.send_message(chatId, "<b>No</b> tienes peticiones pendientes ✅", parse_mode="html")
                time.sleep(BASIC_CONFIG['DELETE_TIME'])
                bot.delete_message(chatId, x.message_id)
                return

            # Iterar sobre los resultados e imprimir la información
            for resultado in resultados:
                film_code, webpage, name, userId = resultado
                url = film_code_to_url(film_code, webpage)
                telegram_link = url_to_telegram_link(url)
                name = telegram_name_with_link(userId, name)
                botones.append(InlineKeyboardButton(f'🗑️ {str(contador)}: {extract_filmname_from_telegram_link(telegram_link)}', callback_data=f'D|{url}'))
                contador += 1

            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌ - Cerrar", callback_data="cerrar"))
            bot.send_message(chatId, textoMensaje, reply_markup=markup, disable_web_page_preview=True, parse_mode="html")

    elif comando in ('/ban', '/unban'):
        """Comando lista"""
        if not is_admin(chatId):
            user_introduces_admin_command(message)
            return;
        userToBanOrUnBan = " ".join(message.text.split()[1:])
        if not userToBanOrUnBan or not userToBanOrUnBan.startswith('@'): 
            # El usuario sólamente ha introducido /ban
            texto = 'Debes introducir el nombre de usuario con el @\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{message.text} @periquito</code>\n\n'
            bot.send_message(chatId, texto, parse_mode="html")
            return 1;

        try:
            if comando in ('/ban'):
                ban_user(userToBanOrUnBan[1:])
                bot.send_message(chatId, f"<b>El usuario {userToBanOrUnBan} ha sido baneado.</b>", parse_mode="html")
            else:
                unban_user(userToBanOrUnBan[1:])
                bot.send_message(chatId, f"<b>El usuario {userToBanOrUnBan} ha sido desbaneado.</b>", parse_mode="html")
        except:
            bot.send_message(chatId, f"<b>No se ha podido banear al usuario {userToBanOrUnBan}.</b>\nNo existe ningún usuario con ese nombre de usuario asociado.", parse_mode="html")

    elif comando in ('/send'):
        if not is_admin(chatId):
            user_introduces_admin_command(message)
            return;

        textoAEnviar = " ".join(message.text.split()[1:])
        if not textoAEnviar: 
            # El usuario sólamente ha introducido /send
            texto = 'Debes introducir algo como mensaje\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{comando} Hola a todos</code>\n\n'
            texto += '<b>Importante</b>: Este mensaje lo recibirán todos aquellos que hayan usado el bot y que no estén baneados.'
            bot.send_message(chatId, texto, parse_mode="html")
            return 1;

        users = get_all_active_users()
        for user in users:
            try:
                if not is_admin(user[0]):
                    bot.send_message(user[0], textoAEnviar, parse_mode="Markdown")
            except:
                debug(f"El usuario {user[0]} no existe actualmente o ha bloqueado al bot")
        bot.send_message(chatId, f'Se ha difundido el mensaje: {textoAEnviar}', parse_mode="Markdown")

    elif comando in ('/sendtouser'):
        if not is_admin(chatId):
            user_introduces_admin_command(message)
            return;

        patron = r'/sendtouser @(\S+) (.+)'
        username = None
        textoAEnviar = None

        # Buscar coincidencias en el texto
        coincidencia = re.match(patron, message.text)

        if coincidencia:
            # El grupo 1 contiene el nombre de usuario, el grupo 2 contiene el mensaje
            username = coincidencia.group(1)
            textoAEnviar = coincidencia.group(2)
        else: 
            # El usuario sólamente ha introducido /sendtouser o algo erroneo
            texto = 'Debes introducir el usuario y el mensaje que deseas enviar\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{comando} @periquito Hola a periquito</code>\n\n'
            texto += '<b>Importante</b>: Este mensaje lo recibirá el destinatario.'
            bot.send_message(chatId, texto, parse_mode="html")
            return 1;

        query = """
            SELECT chat_id
            FROM usuarios
            WHERE username = %s;
        """
        result = executeQuery(query, (username,))[0]
        if not result:
            debug(f"El usuario {username} no se encuentra registrado entre los usuarios.")
            return
        bot.send_message(result[0], textoAEnviar, parse_mode="Markdown")
        bot.send_message(chatId, f'Se ha difundido el mensaje: {textoAEnviar}', parse_mode="Markdown")
    
    elif comando in ('/version'):    
        bot.send_message(chatId, f'<i>Version: {VERSION}</i>', parse_mode="HTML")

    elif not is_admin(chatId):
        """Un usuario normal ha introducido un comando"""
        text_controller(message)

@bot.message_handler(content_types=["text"])
def text_controller(message):
    """Gestiona los mensajes de texto, por aqui entrara el texto que deberan ser exclusivamente peticiones mediante un enlace directo"""
    chatId = message.chat.id
    name = telegram_name_with_link(chatId, message.from_user.first_name)
    update_user(message)
    if not is_user_allowed(chatId):
        bot.send_message(chatId, "Lamentablemente, <b>has sido baneado del bot.</b>", parse_mode="html")
        return
    if message.text.startswith("/"):
        x = bot.send_message(chatId, "Comando no permitido, se reportará al administrador")
        bot.send_message(TELEGRAM_INTERNAL_CHAT, f'{name} ha enviado {message.text}', parse_mode="html")
        time.sleep(BASIC_CONFIG['DELETE_TIME'])
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)
    
    elif "filmaffinity.com" in message.text or "imdb.com" in message.text:
        if is_admin(chatId):
            x = bot.send_message(chatId, "El administrador no puede realizar peticiones")
            time.sleep(BASIC_CONFIG['DELETE_TIME'])
            bot.delete_message(chatId, message.message_id)
            bot.delete_message(chatId, x.message_id)
            return

        # Buscar el primer enlace en el texto
        enlace = obtain_link_from_string(message.text)

        if enlace:
            enlaceEncontrado = enlace.group()
            add_peticion_with_messages(chatId, message.message_id, name, enlaceEncontrado)
        else:
            bot.send_message(chatId, "Enlace no válido.")
            bot.send_message(TELEGRAM_INTERNAL_CHAT, f'{name} ha enviado {message.text}', parse_mode="html")
        
    else:
        x = bot.send_message(chatId, "Este bot no es conversacional, el administrador <b>no recibirá</b> el mensaje si no va junto al enlace de Filmaffinity o IMDb\n\nProcedo a borrar los mensajes", parse_mode="html")
        time.sleep(BASIC_CONFIG['DELETE_TIME'])
        bot.delete_message(chatId, message.message_id)
        bot.delete_message(chatId, x.message_id)

@bot.callback_query_handler(func=lambda mensaje: True)
def button_controller(call):
    """Se ha pulsado un boton"""
    chatId = call.from_user.id
    messageId = call.message.id
    name = telegram_name_with_link(chatId, call.from_user.first_name)

    if call.data == "cerrar":
        bot.delete_message(chatId, messageId)
        delete_user_search(chatId, messageId)
        return

    # Se ha pulsado en un boton de borrar una peticion
    if is_peticion_deletable(call.data):
        filmCode = url_to_film_code(call.data[2:])
        result = get_data_from_peticion(filmCode)
        firstName, userId = result
        username = telegram_name_with_link(userId, firstName)
        previsualizeImage = f'<a href="{read_cache_item_image(call.data[2:])}"> </a>'
        if not is_admin(chatId) and not check_owner_peticion(chatId, filmCode): # El admin puede borrar cualquiera
            bot.delete_message(chatId, messageId)
            bot.send_message(chatId, f'{previsualizeImage}{name}, no tienes permiso para eliminar esa petición ❌', parse_mode="html")
            bot.send_message(TELEGRAM_INTERNAL_CHAT, f'El usuario {name} ha intenado eliminar la petición {filmCode} ❌', parse_mode="html")
            return
        # Borramos la petición
        executeQuery('UPDATE peticiones SET status_id = %s WHERE film_code = %s', (STATUS['DENEGADA'], filmCode), do_commit=True)
        bot.delete_message(chatId, messageId)
        bot.send_message(chatId, f'{previsualizeImage}La petición de {username} ha sido <b>eliminada</b> ✅', parse_mode="html")
        if not is_admin(chatId):
            bot.send_message(TELEGRAM_INTERNAL_CHAT, f'{previsualizeImage}El usuario {name} ha eliminado su petición ❌', parse_mode="html")
        else:
            messageToUser = f"{previsualizeImage}{username}, tu petición: {url_to_telegram_link(call.data[2:])}\n\nHa sido finalmente <b>eliminada</b> por el administrador ❌"
            bot.send_message(userId, messageToUser, parse_mode="html")

    # Se ha pulsado un botón para completar una peticion
    elif is_admin(chatId):
        # Marcamos petición como completada (call.data es una URL)
        filmCode = url_to_film_code(call.data)
        result = get_data_from_peticion(filmCode)
        firstName, userId = result
        username = telegram_name_with_link(userId, firstName)

        executeQuery('UPDATE peticiones SET status_id = %s WHERE film_code = %s', (STATUS['COMPLETADA'], filmCode), do_commit=True)

        previsualizeImage = f'<a href="{read_cache_item_image(call.data)}"> </a>'
        bot.delete_message(chatId, messageId)
        bot.send_message(chatId, f'{previsualizeImage}La petición de {username} ha sido marcada como <b>completada</b> ✅', parse_mode="html")
        messageToUser = f'{previsualizeImage}{username}, tu petición: {url_to_telegram_link(call.data)}\n\n<b>Ha sido completada</b> ✅\n\nTardará unos minutos en aparecer, siempre podrás consultarlo en <i>{NOMBRE_CANAL_NOVEDADES}</i>\nGracias.'
        bot.send_message(userId, messageToUser, parse_mode="html")

    # Dado que el administrador es el único que no puede usar el buscador, solo queda que sea un usuario con los botones de paginación
    else: 
        """Gestiona las pulsaciones de los botones de paginación"""
        # (call.data es una URL)
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

# ==============================================================
# ==============================================================
#  ______ _    _ _   _  _____ _______ _____ ____  _   _  _____ 
# |  ____| |  | | \ | |/ ____|__   __|_   _/ __ \| \ | |/ ____|
# | |__  | |  | |  \| | |       | |    | || |  | |  \| | (___  
# |  __| | |  | | . ` | |       | |    | || |  | | . ` |\___ \ 
# | |    | |__| | |\  | |____   | |   _| || |__| | |\  |____) |
# |_|     \____/|_| \_|\_____|  |_|  |_____\____/|_| \_|_____/ 
#
# ==============================================================
# ==============================================================

def display_page(lista, chatId, pag=0, messageId=None):
    """Crea o edita un mensaje de la página"""
    #Creamos la botonera
    markup = InlineKeyboardMarkup(row_width = BASIC_CONFIG['RESULTADOS_POR_FILA'])
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

def get_data_from_peticion(filmCode):
    query = """
        SELECT u.name, u.chat_id
        FROM peticiones p
        JOIN usuarios u ON p.chat_id = u.chat_id
        WHERE p.film_code = %s;
    """
    result = executeQuery(query, (filmCode,))[0]
    return result

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

def film_code_to_url(filmCode, webpage):
    if webpage == WEBPAGE['FILMAFFINITY']:
        return f'https://www.filmaffinity.com/es/film{filmCode}.html'
    else:
        return f'https://www.imdb.com/title/tt{filmCode}/'

def get_telegram_link(title, url):
    return f'<a href="{url}">{title}</a>'

def telegram_name_with_link(chatId, name):
    return f'<a href="tg://user?id={chatId}">{name}</a>'

def get_all_active_users():
    return executeQuery('SELECT chat_id FROM usuarios WHERE allowed = 1')

def check_owner_peticion(chatId, filmCode):
    result = executeQuery('SELECT COUNT(*) FROM peticiones WHERE chat_id = %s and film_code = %s', (chatId, filmCode))[0][0]
    return True if result != 0 else False

def write_cache_item(title, url, filmCode):
    query = """
        INSERT INTO cache (clave, valor)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE valor = %s
    """
    executeQuery(query, (filmCode, get_telegram_link(str(title).rstrip('\n'), str(url).rstrip('\n')), get_telegram_link(str(title).rstrip('\n'), str(url).rstrip('\n'))), do_commit=True)

def read_cache_item(filmCode):
    return executeQuery('SELECT valor FROM cache WHERE clave = %s', (filmCode,))[0][0]

def write_cache_item_image(urlImage, filmCode):
    query = """
        INSERT INTO cache (clave, valor)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE valor = %s
    """
    executeQuery(query, (f'{filmCode}_img', urlImage, urlImage), do_commit=True)

def read_cache_item_image(url):
    try:
        return executeQuery('SELECT valor FROM cache WHERE clave = %s', (f'{url_to_film_code(url)}_img',))[0][0]
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
    query = """
        INSERT INTO cache (clave, valor)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE valor = %s
    """
    executeQuery(query, (f'{chatId}_{messageId}', json.dumps(datos), json.dumps(datos)), do_commit=True)

def get_user_search(chatId, messageId):
    result = executeQuery('SELECT valor FROM cache WHERE clave = %s', (f'{chatId}_{messageId}',))[0][0]
    return json.loads(result)

def delete_user_search(chatId, messageId):
    executeQuery('DELETE FROM cache WHERE clave = %s', (f'{chatId}_{messageId}',), do_commit=True)

def add_peticion_with_messages(chatId, messageId, name, url):
    linkTelegram = url_to_telegram_link(url)
    bot.delete_message(chatId, messageId) # borramos el mensaje de la petición
    previsualizeImage = f'<a href="{read_cache_item_image(url)}"> </a>'
    try:
        add_peticion(chatId, url)
        bot.send_message(chatId, f'{previsualizeImage}{name}, has solicitado con éxito:\n{linkTelegram}\nNotificado al administrador ✅', parse_mode="html")
        bot.send_message(TELEGRAM_INTERNAL_CHAT, f'{previsualizeImage}Nueva petición de {name}:\n{linkTelegram}', parse_mode="html")
        time.sleep(BASIC_CONFIG['EDIT_TIME'])
    except PeticionExiste as e:
        bot.send_message(chatId, f'{previsualizeImage}{name}, la petición: {url_to_telegram_link(url)} ya se encuentra añadida y está en estado {e.status}.', parse_mode="html")

def add_peticion(chatId, url):
    update = False
    try:
        check_if_exist_peticion(url)
    except PeticionExiste as e:
        if e.code == STATUS['DENEGADA']:
            update = True
        else:
            raise e
    if not update:
        executeQuery('INSERT INTO peticiones (chat_id, film_code, webpage_id, status_id) VALUES (%s, %s, %s, %s)', (chatId, url_to_film_code(url), WEBPAGE['FILMAFFINITY'] if is_filmaffinity_link(url) else WEBPAGE['IMDB'], STATUS['PENDIENTE']), do_commit=True)
    else:
        executeQuery('UPDATE peticiones SET status_id = %s WHERE film_code = %s', (STATUS['PENDIENTE'], url_to_film_code(url)), do_commit=True)

def update_user(call):
    chatId = call.from_user.id
    name = call.from_user.first_name
    username = call.from_user.username
    query = """
        INSERT INTO usuarios (chat_id, name, username)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE name = %s, username = %s
    """
    result = executeQuery(query, (chatId, name, username, name, username), do_commit=True)
    if result == 1:
        bot.send_message(TELEGRAM_INTERNAL_CHAT, f"Se ha actualizado la lista de usuarios con: {telegram_name_with_link(chatId, name)}", parse_mode="html")

def debug(message, html=False):
    print(message)
    if html:
        bot.send_message(TELEGRAM_INTERNAL_CHAT, message, disable_web_page_preview=True, parse_mode="html")
    else:
        bot.send_message(TELEGRAM_INTERNAL_CHAT, message, disable_web_page_preview=True)

def check_if_exist_peticion(url):
    query = """
        SELECT s.id, s.description
        FROM peticiones p
        INNER JOIN status s ON p.status_id = s.id
        WHERE p.film_code = %s
    """
    result = executeQuery(query, (url_to_film_code(url),))
    if result:
        result = result[0]
        raise PeticionExiste(result[0], result[1])

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
    time.sleep(BASIC_CONFIG['DELETE_TIME'])
    bot.delete_message(chatId, x.message_id)

def extract_filmname_from_telegram_link(telegram_link):
    result = re.search(r'>(.*?)</a>', telegram_link)
    if result:
        return result.group(1)
    else:
        return None

def is_user_allowed(chatId):
    result = executeQuery('SELECT allowed FROM usuarios WHERE chat_id = %s', (chatId,))[0][0]
    return bool(result)

def ban_user(username):
    executeQuery('UPDATE usuarios SET allowed = false WHERE username = %s', (username,), do_commit=True)

def unban_user(username):
    executeQuery('UPDATE usuarios SET allowed = true WHERE username = %s', (username,), do_commit=True)

class PeticionExiste(Exception):
    def __init__(self, code, status):
        super().__init__()
        self.status = status
        self.code = code

# =================
# =================
#   _____  ____  
#  |  __ \|  _ \ 
#  | |  | | |_) |
#  | |  | |  _ < 
#  | |__| | |_) |
#  |_____/|____/ 
#
# =================
# =================

def create_tables_default():
    print("Creando tablas si no existen")

    # Verifica si las tablas ya existen
    usuarios_exists = executeQuery("SHOW TABLES LIKE 'usuarios'")
    print(f'TABLE usuarios existe: {usuarios_exists}')

    peticiones_exists = executeQuery("SHOW TABLES LIKE 'peticiones'")
    print(f'TABLE peticiones existe: {peticiones_exists}')

    cache_exists = executeQuery("SHOW TABLES LIKE 'cache'")
    print(f'TABLE cache existe: {cache_exists}')

    status_exist = executeQuery("SHOW TABLES LIKE 'status'")
    print(f'TABLE status existe: {status_exist}')

    webpage_exist = executeQuery("SHOW TABLES LIKE 'webpage'")
    print(f'TABLE webpage existe: {webpage_exist}')
    
    # Si las tablas no existen, créalas
    if not usuarios_exists:
        # Crear tabla de usuarios
        executeQuery("""
            CREATE TABLE usuarios (
                chat_id BIGINT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                allowed BOOLEAN DEFAULT TRUE
            )
        """, do_commit=True)

    if not status_exist:
        # Crear tabla de status
        executeQuery("""
            CREATE TABLE status (
                id INT PRIMARY KEY,
                description VARCHAR(255) NOT NULL
            )
        """, do_commit=True)
        # Insertar valores por defecto solo si no existen
        executeQuery('INSERT INTO status (id, description) SELECT 0, "pendiente" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 0)', do_commit=True)
        executeQuery('INSERT INTO status (id, description) SELECT 1, "completada" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 1)', do_commit=True)
        executeQuery('INSERT INTO status (id, description) SELECT 2, "denegada" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 2)', do_commit=True)

    if not webpage_exist:
        # Crear tabla de status
        executeQuery("""
            CREATE TABLE webpage (
                id INT PRIMARY KEY,
                description VARCHAR(50) NOT NULL
            )
        """, do_commit=True)
        # Insertar valores por defecto solo si no existen
        executeQuery('INSERT INTO webpage (id, description) SELECT 0, "filmaffinity" WHERE NOT EXISTS (SELECT 1 FROM webpage WHERE id = 0)', do_commit=True)
        executeQuery('INSERT INTO webpage (id, description) SELECT 1, "imdb" WHERE NOT EXISTS (SELECT 1 FROM webpage WHERE id = 1)', do_commit=True)

    if not cache_exists:
        # Crear tabla de cache
        executeQuery("""
            CREATE TABLE cache (
                clave VARCHAR(255) PRIMARY KEY,
                valor TEXT
            )
        """, do_commit=True)

    if not peticiones_exists:
        # Crear tabla de peticiones
        executeQuery("""
            CREATE TABLE peticiones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                film_code VARCHAR(255) NOT NULL,
                webpage_id INT NOT NULL,
                status_id INT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES usuarios(chat_id),
                FOREIGN KEY (status_id) REFERENCES status(id),
                FOREIGN KEY (webpage_id) REFERENCES webpage(id)
            )
        """, do_commit=True)
    print("Tablas correctas")

def conectar():
    print("Conectando a BBDD")
    HOST, PORT = DATABASE_HOST.split(":")
    return mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_NAME
    )

def executeQuery(query, values=None, do_commit=False, debug=False):
    mydb = conectar()
    cursor = mydb.cursor()

    if debug:
        if values is not None:
            debug(f'SQL Query: {query}')
            debug(f'SQL Values: {values}')
        else:
            debug(f'SQL Query: {query}')

    try:
        if values is not None:
            cursor.execute(query, values)
        else:
            cursor.execute(query)

        if query.strip().lower().startswith("select") or query.strip().lower().startswith("show"):
            # Devuelve los resultados solo si es una consulta SELECT o SHOW
            results = cursor.fetchall()
            if debug:
                debug(results)
        elif query.strip().lower().startswith("insert") or query.strip().lower().startswith("update"):
            # Devuelve el numero de resultados insertados/actualizados
            results = cursor.rowcount
            if debug:
                debug(results)
        else:
            results = None
    except Exception as e:
        print(f"Error executing query: {e}")
        raise
    finally:
        if do_commit:
            mydb.commit()
        cursor.close()
        mydb.close()

    return results


# ===============================
# ===============================
#   __  __          _____ _   _ 
#  |  \/  |   /\   |_   _| \ | |
#  | \  / |  /  \    | | |  \| |
#  | |\/| | / /\ \   | | | . ` |
#  | |  | |/ ____ \ _| |_| |\  |
#  |_|  |_/_/    \_\_____|_| \_|
#                              
# ===============================
# ===============================

# MAIN
if __name__ == '__main__':
    print(f'Iniciando Bot de peticiones en {SERVER_NAME}')
    time.sleep(10) # Esperamos a la BBDD por si se está arrancando
    create_tables_default()
    bot.set_my_commands([ # Comandos a mostrar en el menú de Telegram
        telebot.types.BotCommand("/start", "Da la bienvenida"),
        telebot.types.BotCommand("/busca", f'Busca en {SEARCH_ENGINE}'),
        telebot.types.BotCommand("/list",  "Utilidad para completar o descartar peticiones"),
        telebot.types.BotCommand("/ban",   "<ADMIN> Utilidad para banear usuarios"),
        telebot.types.BotCommand("/unban", "<ADMIN> Utilidad para desbanear usuarios"),
        telebot.types.BotCommand("/send",  "<ADMIN> Utilidad para escribir a todos los usuarios"),
        telebot.types.BotCommand("/sendtouser", "<ADMIN> Utilidad para escribir a un usuario")
        ])
    bot.infinity_polling() # Arranca la detección de nuevos comandos 
