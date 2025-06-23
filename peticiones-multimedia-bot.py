import os
from config import *
import telebot
import sqlite3
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
from plexapi.server import PlexServer
from datetime import datetime
import time
import requests
import json
import re
import sys

VERSION = "5.0.2"

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

if ("abc" != PLEX_TOKEN and "abc" == PLEX_HOST) or ("abc" == PLEX_TOKEN and "abc" != PLEX_HOST):
    msg = "Si se desa conectarse con Plex, tanto PLEX_HOST como PLEX_TOKEN han de estar correctamente cumplimentadas"
    print(msg)
    sys.exit(1)

def is_plex_linked():
    return "abc" != PLEX_TOKEN and "abc" != PLEX_HOST

# Instanciamos el bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)
if is_plex_linked():
    try:
        plex = PlexServer(PLEX_HOST, PLEX_TOKEN)
    except Exception as e:
        print(f"Error al conectar con Plex, revise los datos de conexion. PLEX_HOST ha de llevar http:// o https://. Error: [{e}]")
        sys.exit(1)

# CONSTANTES NO CONFIGURABLES
BASIC_CONFIG = {
    'RESULTADOS_POR_FILA': 5,
    'DELETE_TIME': 5,
    'EDIT_TIME': 3,
}
STATUS = {
    'NUEVA': -1,
    'PENDIENTE': 0,
    'COMPLETADA': 1,
    'DENEGADA': 2,
}
WEBPAGE = {
    'FILMAFFINITY': 0,
    'IMDB': 1,
}

class User:
    def __init__(self, chatId=None, username=None, name=None, allowed=None):
        self.chatId = chatId
        self.username = username
        self.name = name
        self.allowed = allowed

    def ban(self):
        if not self.is_admin():
            executeQuery('UPDATE usuarios SET allowed = 0 WHERE chat_id = ?', (self.chatId,), do_commit=True)
            self.send_message("<b>❌ Has sido deshabilitado por un administrador.</b>")

    def unban(self):
        executeQuery('UPDATE usuarios SET allowed = 1 WHERE chat_id = ?', (self.chatId,), do_commit=True)
        if not self.is_admin():
            self.send_message("<b>✅ Has sido habilitado por un administrador.</b>")

    def load(self, chatId=None):
        if chatId is None:
            chatId = self.chatId
        result = executeQuery('SELECT chat_id, username, name, allowed FROM usuarios WHERE chat_id = ?', (chatId,))
        if not result:
            debug(f"El usuario {chatId} no se encuentra registrado entre los usuarios.")
            return
        self.chatId, self.username, self.name, self.allowed = result[0]

    def load_by_username(self, username=None):
        if username is None:
            username = self.username
        result = executeQuery('SELECT chat_id, username, name, allowed FROM usuarios WHERE username = ?', (username,))
        if not result:
            debug(f"El usuario {username} no se encuentra registrado entre los usuarios.")
            return
        self.chatId, self.username, self.name, self.allowed = result[0]

    def update(self):
        # Primero verificamos si el usuario existe
        existing = executeQuery('SELECT 1 FROM usuarios WHERE chat_id = ?', (self.chatId,))
        is_new_user = len(existing) == 0

        if self.is_admin():
            query = """
                INSERT INTO usuarios (chat_id, name, username, allowed)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name = excluded.name,
                    username = excluded.username,
                    allowed = 1
            """
            values = (self.chatId, self.name, self.username)
        else:
            query = """
                INSERT INTO usuarios (chat_id, name, username)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name = excluded.name,
                    username = excluded.username
            """
            values = (self.chatId, self.name, self.username)

        executeQuery(query, values, do_commit=True)
        self.load()

        if is_new_user:
            debug(f"Usuario nuevo {self.name}. Habilitado: {self.allowed}. Es admin: {self.is_admin()}")
            if not self.is_admin():
                if not self.allowed:
                    markup = InlineKeyboardMarkup(row_width=1)
                    markup.add(InlineKeyboardButton("✅ Desbloquear usuario", callback_data=f'unban|{self.chatId}'))
                else:
                    markup = None
                send_message_to_admin(f"Un nuevo usuario ha utilizado el bot: {self.get_telegram_link()}", reply_markup=markup)

    def is_admin(self):
        return self.chatId == TELEGRAM_ADMIN
    
    def get_telegram_link(self):
        return f'<a href="tg://user?id={self.chatId}">{self.name}</a>'
    
    def send_message(self, message, parse_mode="html", disable_web_page_preview=False, reply_markup=None):
        if self.is_admin():
            return send_message_to_admin(message, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
        return bot.send_message(self.chatId, message, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)

    def delete_message(self, messageId):
        if self.is_admin():
            bot.delete_message(TELEGRAM_INTERNAL_CHAT, messageId)
            return
        bot.delete_message(self.chatId, messageId)
    
class Media:
    def __init__(self, filmCode=None, title=None, genre=None, rating=None, year=None, webpage=WEBPAGE['FILMAFFINITY'], image=None, isSerie=False):
        self.filmCode=filmCode
        self.title=title
        self.genre=genre
        self.rating=rating
        self.year=year
        self.webpage=webpage
        self.image=image
        self.isSerie=isSerie

    def get_url(self):
        if int(self.webpage) == WEBPAGE['FILMAFFINITY']:
            return f'https://www.filmaffinity.com/es/film{self.filmCode}.html'
        else:
            return f'https://www.imdb.com/title/tt{self.filmCode}/'

    def get_telegram_link(self):
        telegram_link = f'<a href="{self.get_url()}">{self.title} ({self.year})'
        if self.rating != "--":
            telegram_link += f' ({self.rating}★)'
        telegram_link += '</a>'
        return telegram_link
    
    def get_image_previsualize(self):
        return f'<a href="{self.image}">🎥</a> '
    
    def load(self):
        self.title = read_cache_item(self.filmCode, "title")
        self.genre = read_cache_item(self.filmCode, "genre")
        self.rating = read_cache_item(self.filmCode, "rating")
        self.year = read_cache_item(self.filmCode, "year")
        self.image = read_cache_item(self.filmCode, "image")
        self.isSerie = read_cache_item(self.filmCode, "isSerie")

        if not self.title or not self.genre or not self.rating or not self.year or not self.image or self.isSerie is None:
            specificUrl = None
            if int(self.webpage) == WEBPAGE['FILMAFFINITY']:
                specificUrl = f'{URL_BASE_API_FILMAFFINITY}/film?id={self.filmCode}'
            else:
                specificUrl = f'{URL_BASE_API_IMDB}/film?id={self.filmCode}'
            specificData = requests.get(specificUrl).json()
            self.title = specificData.get('title')
            self.genre = specificData.get('genre')
            self.rating = specificData.get('rating')
            self.year = specificData.get('year')
            self.image = specificData.get('image')
            self.isSerie = bool(specificData.get('isSerie', False))
            write_cache_item(self.filmCode, "title", self.title)
            write_cache_item(self.filmCode, "genre", self.genre)
            write_cache_item(self.filmCode, "rating", self.rating)
            write_cache_item(self.filmCode, "year", self.year)
            write_cache_item(self.filmCode, "image", self.image)
            write_cache_item(self.filmCode, "webpage", self.webpage)
            write_cache_item(self.filmCode, "isSerie", self.isSerie)

class Peticion:
    def __init__(self, id=0, user=None, media=None, status=-1):
        self.id = id
        self.user = user
        self.media = media
        self.status = status

    def add(self):
        update = False
        try:
            self.check_if_exist()
        except PeticionExiste as e:
            if (int(e.code) != STATUS['DENEGADA'] and not self.media.isSerie) or (self.media.isSerie and int(e.code) == STATUS['PENDIENTE']):
                raise e
            executeQuery(
                'UPDATE peticiones SET status_id = ?, chat_id = ? WHERE id = ?',
                (STATUS['PENDIENTE'], self.user.chatId, e.id),
                do_commit=True
            )
            update = True

        if not update:
            executeQuery(
                'INSERT INTO peticiones (chat_id, film_code, webpage_id, status_id) VALUES (?, ?, ?, ?)',
                (self.user.chatId, self.media.filmCode, self.media.webpage, STATUS['PENDIENTE']),
                do_commit=True
            )

    def add_with_messages(self):
        try:
            self.add()
            self.user.send_message(
                f'{self.media.get_image_previsualize()}{self.user.name}, has solicitado con éxito:\n{self.media.get_telegram_link()}\nNotificado al administrador ✅'
            )

            url = self.media.get_url()
            markup = InlineKeyboardMarkup(row_width=2)
            botones = [
                InlineKeyboardButton("✅", callback_data=url),
                InlineKeyboardButton("🗑️", callback_data=f'D|{url}')
            ]
            markup.add(*botones)

            x = send_message_to_admin(
                f'{self.media.get_image_previsualize()}Nueva petición de {self.user.get_telegram_link()}:\n{self.media.get_telegram_link()}',
                reply_markup=markup
            )
            write_cache_item(self.media.filmCode, "notification", x.message_id)

        except PeticionExiste as e:
            self.user.send_message(
                f'❌ {self.media.get_image_previsualize()}{self.user.name}, la petición: {self.media.get_telegram_link()} ya se encuentra añadida y está en estado {e.status}.'
            )

    def completar(self):
        executeQuery(
            'UPDATE peticiones SET status_id = ? WHERE id = ?',
            (STATUS['COMPLETADA'], self.id),
            do_commit=True
        )

    def borrar(self):
        executeQuery(
            'UPDATE peticiones SET status_id = ? WHERE id = ?',
            (STATUS['DENEGADA'], self.id),
            do_commit=True
        )

    def load_from_filmCode(self, filmCode):
        query = """
            SELECT p.id, p.film_code, p.webpage_id, p.status_id,
                   u.name, u.username, u.chat_id, u.allowed
            FROM peticiones p
            JOIN usuarios u ON p.chat_id = u.chat_id
            WHERE p.film_code = ?;
        """
        resultado = executeQuery(query, (filmCode,))[0]

        self.user = User(chatId=resultado[6], username=resultado[5], name=resultado[4], allowed=resultado[7])
        self.media = Media(filmCode=resultado[1], webpage=resultado[2])
        self.media.load()
        self.id = resultado[0]
        self.status = resultado[3]

    def add_with_messages_and_plex(self):
        search_results = plex.search(re.sub(r'\([^)]*\)', '', self.media.title))
        debug(f'Búsqueda en Plex: "{self.media.title}" - RESULTADOS: {search_results}')
        if search_results:
            textConfirmation = f"🔎 Se ha encontrado contenido en <b>{SERVER_NAME}</b> que podría coincidir con tu solicitud.\n\n"
            textConfirmation += f"Has querido solicitar: {self.media.get_telegram_link()}\n\n"
            textConfirmation += f"En <b>{SERVER_NAME}</b> se ha encontrado:\n\n"

            contador = 0
            for item in search_results:
                if item.type in ("movie", "show"):
                    textConfirmation += f" · {item.title} ({item.year})\n"
                    contador += 1

            if contador == 0:
                self.add_with_messages()
                return

            textConfirmation += "\nSi lo que quieres pedir no se encuentra entre los resultados, puedes confirmar la petición. En caso contrario puedes cancelarla."
            markup = InlineKeyboardMarkup(row_width=2)
            botones = [
                InlineKeyboardButton("✅ Pedir", callback_data=f'C|{self.media.get_url()}'),
                InlineKeyboardButton("❌ Cancelar", callback_data="cerrar")
            ]
            markup.add(*botones)
            self.user.send_message(textConfirmation, reply_markup=markup, disable_web_page_preview=True)
        else:
            self.add_with_messages()

    def check_if_exist(self):
        query = """
            SELECT id, status_id
            FROM peticiones
            WHERE film_code = ?;
        """
        resultados = executeQuery(query, (self.media.filmCode,))
        for resultado in resultados:
            id, status = resultado
            raise PeticionExiste(
                code=status,
                status=next((estado.lower() for estado, numero in STATUS.items() if numero == status), None),
                id=id
            )

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
@bot.message_handler(commands=["start", "list", "busca", "ban", "unban", "sendtoall", "sendtouser", "version"])
def command_controller(message):
    chatId = message.chat.id
    comando = message.text.split()[0]
    user = User(chatId=message.from_user.id, username=message.from_user.username, name=message.from_user.first_name)
    user.update()
    if not user.username:
        user.send_message(f"⚠️ Por favor {user.name}, para un correcto funcionamiento del bot, <b>es necesario que te establezcas un nombre de usuario</b>.\n\nSe establece en Telegram->Ajustes->Editar->Nombre de usuario.")

    if comando in ('/start', f'/start@{bot.get_me().username}'):
        texto_inicial = ""
        if not user.is_admin():
            """Da la bienvenida al usuario"""
            texto_inicial = f'🎥 Bienvenido al bot de peticiones *{SERVER_NAME}* querido usuario.\n\n'
            texto_inicial += f'A continuación puedes compartir enlaces de [FilmAffinity](https://www.filmaffinity.com/es/main.html) ó [IMDb](https://www.imdb.com) para que se añadan a {SERVER_NAME}\n\n'
            texto_inicial += f'➡️ Comandos disponibles:\n\n'
            texto_inicial += f' · /list Lista tus peticiones pendientes de completar.\n'
            texto_inicial += f' · /busca <Pelicula/Serie> buscará en {SEARCH_ENGINE}.\n'
            texto_inicial += f' · /version Muestra la versión actual.\n'
            if not user.allowed:
                texto_inicial += "\n❌ Lamentablemente, *tu usuario se encuentra deshabilitado por el momento. Contacta con un administrador para que lo habilite.*"
        else:
            """Da la bienvenida al Administrador"""
            texto_inicial = f'🎥 Bienvenido al bot de peticiones *{SERVER_NAME}* querido administrador.\n\n'
            texto_inicial += f'➡️ Comandos disponibles:\n\n'
            texto_inicial += f' · /list Lista las peticiones pendientes de completar.\n'
            texto_inicial += f' · /ban <usuario> deshabilita a un usuario.\n'
            texto_inicial += f' · /unban <usuario> habilita a un usuario.\n'
            texto_inicial += f' · /sendtoall Envía un mensaje a todos los usuarios habilitados.\n'
            texto_inicial += f' · /sendtouser <usuario> envía un mensaje al usuario descrito.\n'
            texto_inicial += f' · /version Muestra la versión actual.\n'
        user.send_message(texto_inicial, parse_mode="markdown", disable_web_page_preview=True)
        return
    
    if not user.allowed:
        user.send_message("❌ Lamentablemente, <b>tu usuario se encuentra deshabilitado por el momento. Contacta con un administrador para que lo habilite.</b>")
        return

    elif comando in ('/busca', f'/busca@{bot.get_me().username}'):
        if user.is_admin():
            x = user.send_message("❌ Esta función está dedicada para los usuarios, <b>no para el administrador.</b>")
            time.sleep(BASIC_CONFIG['DELETE_TIME'])
            user.delete_message(message.message_id)
            user.delete_message(x.message_id)
        else:
            textoBuscar = " ".join(message.text.split()[1:])
            if not textoBuscar: 
                # El usuario sólamente ha introducido /busca
                texto = '❌ Debes introducir algo en la búsqueda\n'
                texto += 'Ejemplo:\n'
                texto += f'<code>{message.text} Gladiator</code>\n\n'
                texto += '<b>Importante</b>: No incluyas el año en la búsqueda'
                user.send_message(texto)
                return 1

            if is_search_engine_filmaffinity():
                elements = filmaffinity_search(textoBuscar)
            else:
                elements = imdb_search(textoBuscar)
            if not elements:
                user.send_message("❌ Lamentablemente, <b>no se han encontrado</b> resultados para el texto introducido\nRecuerda que <b>no debes</b> introducir el año en el texto de búsqueda")
            else:
                display_page(elements, chatId)
    
    elif comando in ('/list', f'/list@{bot.get_me().username}'):
        """Comando lista"""
        user.delete_message(message.message_id)
        if user.is_admin():
            markup = InlineKeyboardMarkup(row_width = 3)
            textoMensaje = "📃 <b>Completa</b> o <b>descarta</b> peticiones:\n"
            contador = 1
            botones = []
            peticiones = get_all_pending_peticiones()

            if len(peticiones) == 0:
                x = user.send_message("<b>No</b> hay peticiones pendientes ✅")
                time.sleep(BASIC_CONFIG['DELETE_TIME'])
                user.delete_message(x.message_id)
                return

            # Iterar sobre los resultados e imprimir la información
            for peticion in peticiones:
                url = peticion.media.get_url()
                telegram_link = peticion.media.get_telegram_link()
                name = peticion.user.get_telegram_link()
                textoMensaje += f'<b>[{str(contador)}]</b> {name} : {telegram_link} \n'
                botones.append(InlineKeyboardButton(f'{str(contador)}: {peticion.media.title}', url=url))
                botones.append(InlineKeyboardButton("✅", callback_data=url))
                botones.append(InlineKeyboardButton("🗑️", callback_data=f'D|{url}'))
                contador += 1

            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌ - Cerrar", callback_data="cerrar"))
            user.send_message(textoMensaje, reply_markup=markup, disable_web_page_preview=True)
        else:
            markup = InlineKeyboardMarkup(row_width = 2)
            textoMensaje = "<b>Descarta</b> tus peticiones haciendo clic la 🗑️.\n\nSi no quieres eliminar ninguna pulsa en <code>Cerrar</code>.\n"
            contador = 1
            botones = []

            peticiones = get_all_pending_peticiones_from_user(user)

            if len(peticiones) == 0:
                x = user.send_message("<b>No</b> tienes peticiones pendientes ✅")
                time.sleep(BASIC_CONFIG['DELETE_TIME'])
                user.delete_message(x.message_id)
                return

            # Iterar sobre los resultados e imprimir la información
            for peticion in peticiones:
                url = peticion.media.get_url()
                telegram_link = peticion.media.get_telegram_link()
                name = peticion.user.get_telegram_link()
                botones.append(InlineKeyboardButton(f'{str(contador)}: {peticion.media.title}', url=url))
                botones.append(InlineKeyboardButton(f'🗑️', callback_data=f'D|{url}'))
                contador += 1

            markup.add(*botones)
            markup.add(InlineKeyboardButton("❌ - Cerrar", callback_data="cerrar"))
            user.send_message(textoMensaje, reply_markup=markup, disable_web_page_preview=True)

    elif comando in ('/ban', f'/ban@{bot.get_me().username}', '/unban', f'/unban@{bot.get_me().username}'):
        """Comando lista"""
        if not user.is_admin():
            user_introduces_admin_command(message)
            return
        
        userToBanOrUnBan = " ".join(message.text.split()[1:])
        if not userToBanOrUnBan or not userToBanOrUnBan.startswith('@'): 
            # El usuario sólamente ha introducido /ban
            texto = '❌ Debes introducir el nombre de usuario con el @\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{comando} @periquito</code>\n\n'
            user.send_message(texto)
            return 1

        try:
            if comando in ('/ban'):
                userToBan = User(username=userToBanOrUnBan[1:])
                userToBan.load_by_username()
                userToBan.ban()
                user.send_message(f"⚠️ <b>El usuario {userToBan.get_telegram_link()} ha sido deshabilitado.</b>")
            else:
                userToUnban = User(username=userToBanOrUnBan[1:])
                userToUnban.load_by_username()
                userToUnban.unban()
                user.send_message(f"⚠️ <b>El usuario {userToUnban.get_telegram_link()} ha sido habilitado.</b>")
        except:
            user.send_message(f"<b>No se ha podido deshabilitar el usuario {userToBanOrUnBan}.</b>\nNo existe ningún usuario con ese nombre de usuario asociado.")

    elif comando in ('/sendtoall', f'/sendtoall@{bot.get_me().username}'):
        if not user.is_admin():
            user_introduces_admin_command(message)
            return

        textoAEnviar = " ".join(message.text.split()[1:])
        if not textoAEnviar: 
            # El usuario sólamente ha introducido /send
            texto = '❌ Debes introducir algo como mensaje\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{comando} Hola a todos</code>\n\n'
            texto += '<b>Importante</b>: Este mensaje lo recibirán todos aquellos usuarios habilitados que hayan usado el bot.'
            user.send_message(texto)
            return 1

        users = get_all_active_users()
        for userToSend in users:
            try:
                if not userToSend.is_admin():
                    userToSend.send_message(textoAEnviar, "Markdown")
            except:
                debug(f"El usuario {userToSend.name} (@{userToSend.username}) no existe actualmente o ha bloqueado al bot")
        user.send_message(f'Se ha difundido el mensaje: {textoAEnviar}', parse_mode="Markdown")

    elif comando in ('/sendtouser', f'/sendtouser@{bot.get_me().username}'):
        if not user.is_admin():
            user_introduces_admin_command(message)
            return

        patron = r'/sendtouser @(\S+) (.+)'
        username = None
        textoAEnviar = None
        coincidencia = re.match(patron, message.text)

        if coincidencia:
            username = coincidencia.group(1)
            textoAEnviar = coincidencia.group(2)
        else: 
            # El usuario sólamente ha introducido /sendtouser o algo erroneo
            texto = '❌ Debes introducir el usuario y el mensaje que deseas enviar\n'
            texto += 'Ejemplo:\n'
            texto += f'<code>{comando} @periquito Hola a periquito</code>\n\n'
            texto += '<b>Importante</b>: Este mensaje lo recibirá el destinatario.'
            user.send_message(texto)
            return 1

        userToSend = User(username=username)
        userToSend.load_by_username()
        if not userToSend.chatId:
            user.send_message(f"El usuario {username} no se encuentra registrado entre los usuarios.")
            debug(f"El usuario {username} no se encuentra registrado entre los usuarios.")
            return
        else:
            userToSend.send_message(textoAEnviar, "Markdown")
        user.send_message(f'Se ha difundido el mensaje a {userToSend.name}: {textoAEnviar}', parse_mode="Markdown")
    
    elif comando in ('/version', f'/version@{bot.get_me().username}'):
        user.delete_message(message.id)
        x = user.send_message(f'⚙️ _Versión: {VERSION}_\nDesarrollado con ❤️ por @dgongut\n\nSi encuentras cualquier fallo o sugerencia contáctame.\n\nPuedes encontrar todo lo relacionado con este bot en [DockerHub](https://hub.docker.com/r/dgongut/peticiones-multimedia-bot) o en [GitHub](https://github.com/dgongut/peticiones-multimedia-bot)', parse_mode="markdown")
        time.sleep(15)
        user.delete_message(x.message_id)

    elif not user.is_admin():
        """Un usuario normal ha introducido un comando"""
        text_controller(message)

@bot.message_handler(content_types=["text"])
def text_controller(message):
    """Gestiona los mensajes de texto, por aqui entrara el texto que deberan ser exclusivamente peticiones mediante un enlace directo"""
    chatId = message.chat.id
    user = User(chatId=message.from_user.id, username=message.from_user.username, name=message.from_user.first_name)
    user.update()
    if not user.username:
        user.send_message(f"⚠️ Por favor {user.get_telegram_link()}, para un correcto funcionamiento del bot, <b>es necesario que te establezcas un nombre de usuario</b>.\n\nSe establece en Telegram->Ajustes->Editar->Nombre de usuario.")

    if not user.allowed:
        user.send_message("❌ Lamentablemente, <b>tu usuario se encuentra deshabilitado por el momento. Contacta con un administrador para que lo habilite.</b>")
        return
    
    if message.text.startswith("/"):
        if user.is_admin():
            return
        x = user.send_message("❌ Comando no permitido, se reportará al administrador")
        send_message_to_admin(f'⚠️ <b>{user.name} ha enviado {message.text}</b>')
        time.sleep(BASIC_CONFIG['DELETE_TIME'])
        user.delete_message(message.message_id)
        user.delete_message(x.message_id)
    
    elif "filmaffinity.com" in message.text or "imdb.com" in message.text:
        user.delete_message(message.message_id)
        if user.is_admin():
            x = user.send_message("❌ El administrador no puede realizar peticiones")
            time.sleep(BASIC_CONFIG['DELETE_TIME'])
            user.delete_message(x.message_id)
            return

        # Buscar el primer enlace en el texto
        enlace = obtain_link_from_string(message.text)

        if enlace:
            enlaceEncontrado = enlace.group()
            if is_filmaffinity_link(enlaceEncontrado):
                webpage = WEBPAGE['FILMAFFINITY']
            else:
                webpage = WEBPAGE['IMDB']
            media = Media(filmCode=url_to_film_code(enlaceEncontrado), webpage=webpage)
            media.load()
            peticion = Peticion(user=user, media=media)
            if not is_plex_linked():
                peticion.add_with_messages()
            else:
                peticion.add_with_messages_and_plex()
        else:
            user.send_message("❌ Enlace no válido.")
            send_message_to_admin(f'{user.get_telegram_link} ha enviado {message.text}')
        
    else:
        x = user.send_message("❌ Este bot no es conversacional, el administrador <b>no recibirá</b> el mensaje si no va junto al enlace de Filmaffinity o IMDb\n\nProcedo a borrar los mensajes", parse_mode="html")
        time.sleep(BASIC_CONFIG['DELETE_TIME'])
        user.delete_message(message.message_id)
        user.delete_message(x.message_id)

@bot.callback_query_handler(func=lambda mensaje: True)
def button_controller(call):
    """Se ha pulsado un boton"""
    messageId = call.message.id
    user = User(chatId=call.from_user.id, username=call.from_user.username, name=call.from_user.first_name)
    user.update()

    if call.data == "cerrar":
        user.delete_message(messageId)
        delete_user_search(user.chatId, messageId)
        return
    
    if call.data.startswith('unban|'):
        user.delete_message(messageId)
        if user.is_admin():
            userToUnban = User(chatId=call.data.replace('unban|', ''))
            userToUnban.load()
            userToUnban.unban()
            user.send_message(f"⚠️ <b>El usuario {userToUnban.get_telegram_link()} ha sido habilitado.</b>")
            return
        else:
            send_message_to_admin(f'El usuario {user.get_telegram_link()} ha tratado de habilitar a un usuario. Esto no debería pasar.')
            return

    # Se ha pulsado en un boton de borrar una peticion
    if is_peticion_deletable(call.data):
        filmCode = url_to_film_code(call.data[2:])
        peticion = Peticion()
        peticion.load_from_filmCode(filmCode=filmCode)
        if not user.is_admin() and user.chatId != peticion.user.chatId: # El admin puede borrar cualquiera
            user.delete_message(messageId)
            user.send_message(f'{peticion.media.get_image_previsualize()}{user.name}, no tienes permiso para eliminar esa petición ❌')
            send_message_to_admin(f'El usuario {user.get_telegram_link()} ha intenado eliminar la petición {filmCode} ❌')
            return
        peticion.borrar()
        notificationMessage = read_cache_item(peticion.media.filmCode, "notification")
        if (notificationMessage and notificationMessage != messageId):
            try:
                bot.delete_message(TELEGRAM_INTERNAL_CHAT, notificationMessage)
            except:
                pass
        try:
            user.delete_message(messageId)
        except:
            pass
        user.send_message(f'{peticion.media.get_image_previsualize()}La petición de {peticion.user.get_telegram_link()} ha sido <b>eliminada</b> ✅')
        if not user.is_admin():
            send_message_to_admin(f'{peticion.media.get_image_previsualize()}El usuario {user.get_telegram_link()} ha eliminado su petición ❌')
        else:
            messageToUser = f"{peticion.media.get_image_previsualize()}{peticion.user.name}, tu petición: {peticion.media.get_telegram_link()}\n\nHa sido finalmente <b>eliminada</b> por el administrador ❌"
            peticion.user.send_message(messageToUser)

    # Se ha pulsado un botón para completar una peticion
    elif user.is_admin():
        # Marcamos petición como completada (call.data es una URL)
        filmCode = url_to_film_code(call.data)
        peticion = Peticion()
        peticion.load_from_filmCode(filmCode=filmCode)
        peticion.completar()
        notificationMessage = read_cache_item(peticion.media.filmCode, "notification")
        if (notificationMessage and notificationMessage != messageId):
            try:
                bot.delete_message(TELEGRAM_INTERNAL_CHAT, notificationMessage)
            except:
                pass
        try:
            user.delete_message(messageId)
        except:
            pass
        user.send_message(f'{peticion.media.get_image_previsualize()}La petición de {peticion.user.get_telegram_link()} ha sido marcada como <b>completada</b> ✅')
        messageToUser = f'{peticion.media.get_image_previsualize()}{peticion.user.name}, tu petición: {peticion.media.get_telegram_link()}\n\n<b>Ha sido completada</b> ✅\n\nTardará un tiempo en estar disponible. Siempre podrás consultarlo en <i>{NOMBRE_CANAL_NOVEDADES}</i>\nGracias.'
        peticion.user.send_message(messageToUser)

    # Dado que el administrador es el único que no puede usar el buscador, solo queda que sea un usuario con los botones de paginación
    else: 
        """Gestiona las pulsaciones de los botones de paginación"""
        # (call.data es una URL o una peticion confirmada empezando por C|
        if call.data in ("anterior", "siguiente"):
            datos = get_user_search(user.chatId, messageId)
            if call.data == "anterior":
                if datos["pag"] == 0:
                    bot.answer_callback_query(call.id, "Ya estás en la primera página")
                
                else:
                    datos["pag"] -= 1
                    set_user_search(user.chatId, messageId, datos)
                    display_page(datos["lista"], user.chatId, datos["pag"], messageId)
                return
            
            elif call.data == "siguiente":
                if datos["pag"] * RESULTADOS_POR_PAGINA + RESULTADOS_POR_PAGINA >= len(datos["lista"]):
                    bot.answer_callback_query(call.id, "Ya estás en la última página")
                
                else:
                    datos["pag"] += 1
                    set_user_search(user.chatId, messageId, datos)
                    display_page(datos["lista"], user.chatId, datos["pag"], messageId)
                return
        else:
            delete_user_search(user.chatId, messageId)
            user.delete_message(messageId)
            url = call.data
            is_already_confirmed = is_peticion_confirmed(call.data)
            if is_already_confirmed:
                url = call.data[2:]
            filmCode = url_to_film_code(url=url)
            if is_filmaffinity_link(url):
                webpage = WEBPAGE['FILMAFFINITY']
            else:
                webpage = WEBPAGE['IMDB']
            media = Media(filmCode=filmCode, webpage=webpage)
            media.load()
            peticion = Peticion(user=user, media=media)
            if is_already_confirmed or not is_plex_linked():
                peticion.add_with_messages()
            elif is_plex_linked():
                peticion.add_with_messages_and_plex()

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
            filmaffinityElements.append([title, url])
            write_cache_item(item['id'], "title", item['title'])
            write_cache_item(item['id'], "rating", item['rating'])
            write_cache_item(item['id'], "year", item['year'])
            write_cache_item(item['id'], "image", item['image'])
            write_cache_item(item['id'], "webpage", WEBPAGE['FILMAFFINITY'])

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
            imdbElements.append([title, url])
            write_cache_item(item['id'], "title", item['title'])
            write_cache_item(item['id'], "year", item['year'])
            write_cache_item(item['id'], "image", item['image'])
            write_cache_item(item['id'], "webpage", WEBPAGE['IMDB'])

    elif response.status_code == 404:
        return imdbElements
    else:
        # La solicitud no fue exitosa
        debug(f"Error al realizar la solicitud [{searchText}] a la API IMDb. Código de respuesta:", response.status_code)
    
    return imdbElements

def get_all_pending_peticiones():
    query = """
        SELECT film_code
        FROM peticiones
        WHERE status_id = ?;
    """
    peticiones = []
    resultados = executeQuery(query, (STATUS['PENDIENTE'],))

    for (filmCode,) in resultados:
        peticion = Peticion()
        peticion.load_from_filmCode(filmCode)
        peticiones.append(peticion)
    
    return peticiones

def get_all_pending_peticiones_from_user(user):
    query = """
        SELECT film_code
        FROM peticiones
        WHERE status_id = ? AND chat_id = ?;
    """
    resultados = executeQuery(query, (STATUS['PENDIENTE'], user.chatId))
    peticiones = []

    for (filmCode,) in resultados:
        peticion = Peticion()
        peticion.load_from_filmCode(filmCode)
        peticiones.append(peticion)
    
    return peticiones

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

def get_all_active_users():
    users = []
    results = executeQuery('SELECT chat_id, name, username, allowed FROM usuarios WHERE allowed = 1')

    for userFromDB in results:
        user = User(chatId=userFromDB[0], name=userFromDB[1], username=userFromDB[2], allowed=userFromDB[3])
        users.append(user)
    return users

def write_cache_item(filmCode, property, valor):
    clave = f'{filmCode}_{property}'
    query = """
        INSERT OR REPLACE INTO cache (clave, valor)
        VALUES (?, ?)
    """
    executeQuery(query, (clave, valor), do_commit=True)

def read_cache_item(filmCode, property):
    clave = f'{filmCode}_{property}'
    try:
        return executeQuery('SELECT valor FROM cache WHERE clave = ?', (clave,))[0][0]
    except IndexError:
        return None

def set_user_search(chatId, messageId, datos):
    clave = f'{chatId}_{messageId}'
    valor_json = json.dumps(datos)
    query = """
        INSERT OR REPLACE INTO cache (clave, valor)
        VALUES (?, ?)
    """
    executeQuery(query, (clave, valor_json), do_commit=True)

def get_user_search(chatId, messageId):
    clave = f'{chatId}_{messageId}'
    try:
        result = executeQuery('SELECT valor FROM cache WHERE clave = ?', (clave,))[0][0]
        return json.loads(result)
    except IndexError:
        return None

def delete_user_search(chatId, messageId):
    clave = f'{chatId}_{messageId}'
    executeQuery('DELETE FROM cache WHERE clave = ?', (clave,), do_commit=True)

def debug(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - DEBUG: {message}')

def error(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - ERROR: {message}')

def warning(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - ATENCION: {message}')

def obtain_link_from_string(text):
    pattern = r"https?://[^\s]+"
    return re.search(pattern, text)

def is_peticion_deletable(peticion):
    # Las peticiones que están marcadas para borrar comienzan con D|
    return peticion.startswith('D|')

def is_peticion_confirmed(peticion):
    # Las peticiones que están confirmadas por el usuario comienzan con C|
    return peticion.startswith('C|')

def is_search_engine_filmaffinity():
    return SEARCH_ENGINE == "filmaffinity"

def is_filmaffinity_link(link):
    return "filmaffinity" in link

def send_message_to_admin(message, parse_mode="html", disable_web_page_preview=False, reply_markup=None):
    return bot.send_message(TELEGRAM_INTERNAL_CHAT, message, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)

def user_introduces_admin_command(message):
    chatId = message.chat.id
    bot.delete_message(chatId, message.message_id)
    x = bot.send_message(chatId, f'El comando {message.text} está reservado al administrador', parse_mode="html", disable_web_page_preview=True)
    time.sleep(BASIC_CONFIG['DELETE_TIME'])
    bot.delete_message(chatId, x.message_id)

class PeticionExiste(Exception):
    def __init__(self, code, status, id):
        super().__init__()
        self.status = status
        self.code = code
        self.id = id

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

def table_exists(table_name):
    result = executeQuery(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return bool(result)

def create_tables_default():
    debug("Creando tablas si no existen")

    usuarios_exists = table_exists("usuarios")
    peticiones_exists = table_exists("peticiones")
    cache_exists = table_exists("cache")
    status_exist = table_exists("status")
    webpage_exist = table_exists("webpage")

    if not usuarios_exists:
        executeQuery("""
            CREATE TABLE usuarios (
                chat_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT,
                allowed INTEGER DEFAULT 0
            )
        """, do_commit=True)
        executeQuery("CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);", do_commit=True)

    if not status_exist:
        executeQuery("""
            CREATE TABLE status (
                id INTEGER PRIMARY KEY,
                description TEXT NOT NULL
            )
        """, do_commit=True)

        executeQuery('INSERT INTO status (id, description) SELECT 0, "pendiente" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 0)', do_commit=True)
        executeQuery('INSERT INTO status (id, description) SELECT 1, "completada" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 1)', do_commit=True)
        executeQuery('INSERT INTO status (id, description) SELECT 2, "denegada" WHERE NOT EXISTS (SELECT 1 FROM status WHERE id = 2)', do_commit=True)

    if not webpage_exist:
        executeQuery("""
            CREATE TABLE webpage (
                id INTEGER PRIMARY KEY,
                description TEXT NOT NULL
            )
        """, do_commit=True)

        executeQuery('INSERT INTO webpage (id, description) SELECT 0, "filmaffinity" WHERE NOT EXISTS (SELECT 1 FROM webpage WHERE id = 0)', do_commit=True)
        executeQuery('INSERT INTO webpage (id, description) SELECT 1, "imdb" WHERE NOT EXISTS (SELECT 1 FROM webpage WHERE id = 1)', do_commit=True)

    if not cache_exists:
        executeQuery("""
            CREATE TABLE cache (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        """, do_commit=True)

    if not peticiones_exists:
        executeQuery("""
            CREATE TABLE peticiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                film_code TEXT NOT NULL,
                webpage_id INTEGER NOT NULL,
                status_id INTEGER NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES usuarios(chat_id),
                FOREIGN KEY (status_id) REFERENCES status(id),
                FOREIGN KEY (webpage_id) REFERENCES webpage(id)
            )
        """, do_commit=True)
        executeQuery("CREATE INDEX IF NOT EXISTS idx_peticiones_film_code ON peticiones(film_code);", do_commit=True)

    debug("Tablas correctas")

conn = None

def conectar():
    global conn
    if conn is None:
        conn = sqlite3.connect(FICHERO_SQLITE, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
    return conn

def executeQuery(query, values=None, do_commit=False, debugging=False):
    conn = conectar()
    cursor = conn.cursor()

    if debugging:
        debug(f'SQL Query: {query}')
        if values:
            debug(f'SQL Values: {values}')

    try:
        if values is not None:
            cursor.execute(query, values)
        else:
            cursor.execute(query)

        if query.strip().lower().startswith(("select", "pragma")):
            results = cursor.fetchall()
        elif query.strip().lower().startswith(("insert", "update", "delete")):
            results = cursor.rowcount
        else:
            results = None

        if do_commit:
            conn.commit()
    except Exception as e:
        print(f"Error executing query: {e}")
        raise
    finally:
        cursor.close()

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
    debug(f'Iniciando Bot de peticiones en {SERVER_NAME}')
    create_tables_default()
    bot.set_my_commands([ # Comandos a mostrar en el menú de Telegram
        telebot.types.BotCommand("/start", "Da la bienvenida"),
        telebot.types.BotCommand("/busca", f'Busca en {SEARCH_ENGINE}'),
        telebot.types.BotCommand("/list", "Utilidad para completar o descartar peticiones"),
        telebot.types.BotCommand("/ban", "<ADMIN> Utilidad para deshabilitar usuarios"),
        telebot.types.BotCommand("/unban", "<ADMIN> Utilidad para habilitar usuarios"),
        telebot.types.BotCommand("/sendtoall", "<ADMIN> Utilidad para escribir a todos los usuarios"),
        telebot.types.BotCommand("/sendtouser", "<ADMIN> Utilidad para escribir a un usuario"),
        telebot.types.BotCommand("/version", "Consulta la versión actual del programa")
        ])
    starting_message = f"🎥 *Peticiones Multimedia\n🟢 Activo*\n_⚙️ v{VERSION}_"
    send_message_to_admin(message=starting_message, parse_mode="markdown")
    bot.infinity_polling() # Arranca la detección de nuevos comandos 
