# peticiones-multimedia-bot

Lleva el control de las peticiones multimedia de tu servidor desde un único lugar.
Deja que tus familiares y amigos añadan peticiones de la forma más cómoda:
 - ¿Buscador integrado? ✅
 - ¿Enlaces directos? ✅
 - Filmaffinity e IMDb de manera simultánea ✅

¿Lo buscas en [docker](https://hub.docker.com/r/dgongut/peticiones-multimedia-bot)?

### Funciones

Como usuario:
 - Tienes la posibilidad de añadir una petición de una película o serie. Tan sencillo como mandar un enlace de FilmAffinity/IMDb o usar el buscador integrado.

Como administrador:
 - Puedes llevar un control de las peticiones pendientes, confirmarlas o descartarlas.

### Configuración en config.py
                    
| CLAVE  | OBLIGATORIO | VALOR |
|:------------- |:---------------:| :-------------|
|TELEGRAM_TOKEN |✅| Token del bot |
|TELEGRAM_ADMIN |✅| ChatId del administrador (se puede obtener hablándole al bot Rose escribiendo /id) | 
|TELEGRAM_INTERNAL_CHAT |❌| ChatId de un grupo o canal, en el caso de que se quiera notificar de nuevas peticiones en un chat diferente al del administrador |
|SERVER_NAME |✅| Nombre del servidor |
|SEARCH_ENGINE |❌| filmaffinity ó imdb (por defecto filmaffinity) |
|NOMBRE_CANAL_NOVEDADES |❌| Nombre del canal donde se publiquen las novedades, de no ponerse será "Novedades en "SERVER_NAME"" |
|RESULTADOS_POR_PAGINA |❌| Indica cuántos resultados mostrar por página en el buscador integrado de Filmaffinity (10 por defecto) |
