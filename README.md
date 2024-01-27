# peticiones-multimedia-bot

Lleva el control de las peticiones multimedia de tu servidor desde un único lugar.
Deja que tus familiares y amigos añadan peticiones de la forma más cómoda:
 - ¿Buscador integrado? ✅
 - ¿Enlaces directos? ✅
 - Filmaffinity e IMDb de manera simultánea ✅
 - Integración con Plex ✅

¿Lo buscas en [docker](https://hub.docker.com/r/dgongut/peticiones-multimedia-bot)?

## Funciones

Como usuario:
 - Añade peticiones de una películas o series. Tan sencillo como mandar un enlace de FilmAffinity/IMDb o usar el buscador integrado.
 - Tienes la posibilidad de gestionar tus peticiones para eliminarlas.

Como administrador:
 - Puedes llevar un control de las peticiones pendientes, confirmarlas o descartarlas.
 - Puedes banear y desbanear usuarios
 - Puedes enviar mensajes a todos los usuarios o a un único usuario

## Configuración en config.py
                    
| CLAVE  | OBLIGATORIO | VALOR |
|:------------- |:---------------:| :-------------|
|TELEGRAM_TOKEN |✅| Token del bot |
|TELEGRAM_ADMIN |✅| ChatId del administrador (se puede obtener hablándole al bot Rose escribiendo /id) | 
|TELEGRAM_INTERNAL_CHAT |❌| ChatId de un grupo o canal, en el caso de que se quiera notificar de nuevas peticiones en un chat diferente al del administrador |
|SERVER_NAME |✅| Nombre del servidor |
|HOST_FILMAFFINITY_API |✅| *(>v2.0)* Host y puerto de la [API de consulta a Filmaffinity](https://github.com/dgongut/filmaffinity-api) |
|HOST_IMDB_API |✅| *(>v2.0)* Host y puerto de la [API de consulta a IMDB](https://github.com/dgongut/imdb-api) |
|DATABASE_USER |✅| *(>v3.0)* Usuario de la BBDD MariaDB |
|DATABASE_PASSWORD |✅| *(>v3.0)* Contraseña de la BBDD MariaDB |
|DATABASE_NAME |✅| *(>v3.0)* Nombre de la BBDD MariaDB |
|DATABASE_HOST |✅| *(>v3.0)* Host y puerto (IP:PUERTO) de la BBDD MariaDB |
|SEARCH_ENGINE |❌| filmaffinity ó imdb (por defecto filmaffinity) |
|NOMBRE_CANAL_NOVEDADES |❌| Nombre del canal donde se publiquen las novedades, de no ponerse será "Novedades en "SERVER_NAME"" |
|RESULTADOS_POR_PAGINA |❌| Indica cuántos resultados mostrar por página en el buscador integrado de Filmaffinity (10 por defecto) |
|PLEX_HOST |❌| *(>v4.0)* Host donde este instalado Plex, por ejemplo http://192.168.1.50:32400 |
|PLEX_TOKEN |❌| *(>v4.0)* TOKEN de sesión de Plex, se puede obtener [así](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)|

### Anotaciones
Tras la versión 3.0 se ha cambiado la manera en la que se guardan las peticiones. Ya no se guardarán en dos ficheros txt, sino que se guardarán en una BBDD MariaDB. Para facilitar la migración, [he creado un script en python](https://github.com/dgongut/migracion-peticiones-bot-v3).


## Ejemplo docker-compose.yaml
```yaml
version: '3.3'
services:
    filmaffinity-api:
        container_name: filmaffinity-api
        image: dgongut/filmaffinity-api:latest
        networks:
          - peticiones_bot_network
    imdb-api:
        container_name: imdb-api
        image: dgongut/imdb-api:latest
        networks:
          - peticiones_bot_network
    mariadb:
        container_name: peticiones-mariadb
        environment:
            - MARIADB_USER=userdb
            - MARIADB_PASSWORD=my_cool_secret
            - MARIADB_DATABASE=exmple-database
            - MARIADB_ROOT_PASSWORD=my-secret-pw
        volumes:
          - /base/de/datos/en/el/host/:/config
        networks:
          - peticiones_bot_network
        image: mariadb:latest
    peticiones-multimedia-bot:
        container_name: peticiones-multimedia-bot
        environment:
          - TELEGRAM_TOKEN=xxx
          - TELEGRAM_INTERNAL_CHAT=xxx #OPTIONAL
          - TELEGRAM_ADMIN=xxx
          - SERVER_NAME="MY SERVER"
          - NOMBRE_CANAL_NOVEDADES="MI CANAL DE NOVEDADES" #OPCIONAL
          - RESULTADOS_POR_PAGINA=10 #OPCIONAL
          - SEARCH_ENGINE=filmaffinity
          - HOST_FILMAFFINITY_API=filmaffinity-api:22049
          - HOST_IMDB_API=imdb-api:22048
          - DATABASE_USER=userdb
          - DATABASE_PASSWORD=my_cool_secret
          - DATABASE_NAME=exmple-database
          - DATABASE_HOST=mariadb:3306
          #- PLEX_HOST=http://192.168.1.50:32400 #OPCIONAL
          #- PLEX_TOKEN=ilhjadflhk3414jh #OPCIONAL
        image: dgongut/peticiones-multimedia-bot:latest
        networks:
          - peticiones_bot_network
        tty: true
networks:
    peticiones_bot_network:
```