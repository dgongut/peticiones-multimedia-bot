# peticiones-multimedia-bot

Lleva el control de las peticiones multimedia de tu servidor desde un único lugar.
Deja que tus familiares y amigos añadan peticiones de la forma más cómoda:
 - ¿Buscador integrado? ✅
 - ¿Enlaces directos? ✅
 - Filmaffinity e IMDb de manera simultánea ✅

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

### Anotaciones
Tras la versión 3.0 se ha cambiado la manera en la que se guardan las peticiones. Ya no se guardarán en dos ficheros txt, sino que se guardarán en una BBDD MariaDB. Para facilitar la migración, [he creado un script en python](https://github.com/dgongut/migracion-peticiones-bot-v3).