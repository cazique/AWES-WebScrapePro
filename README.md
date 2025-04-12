# AWES-WebScrapePro
# Importador WordPress Optimizado

## Descripción

Este proyecto implementa un importador avanzado para WordPress con mejoras significativas en seguridad, modularización y funcionalidades. Permite importar contenido desde diversas fuentes (principalmente feeds RSS) a WordPress, con soporte para posts estándar, páginas y productos WooCommerce.

### Características principales

- **Seguridad mejorada**: Manejo seguro de credenciales, protección contra inyección SQL y sanitización de contenido.
- **Arquitectura modular**: Código organizado siguiendo principios SOLID para facilitar mantenimiento y ampliaciones.
- **Importación selectiva**: Soporte para posts regulares, páginas y productos WooCommerce con sus metadatos.
- **Rotación de proxies**: Sistema para distribuir peticiones a través de diferentes IPs.
- **Sistema de plantillas**: Integración con Jinja2 para transformar o enriquecer el contenido antes de importarlo.
- **Procesamiento de imágenes**: Optimización y extracción de metadatos EXIF con Pillow.
- **Exportación de estadísticas**: Generación de reportes en formato CSV y JSON.
- **Ejecución asíncrona**: Procesamiento paralelo mediante ThreadPoolExecutor para mejorar rendimiento.
- **Compatible con Docker**: Fácil despliegue en contenedores.

## Estructura del Proyecto

```
wp_importer_project/
├── wp_importer/
│   ├── __init__.py        # Inicialización del paquete
│   ├── config.py          # Gestión de configuración
│   ├── database.py        # Interacción con base de datos SQLite
│   ├── wordpress_api.py   # Funciones para API REST WordPress/WooCommerce
│   ├── content_processor.py # Procesamiento de contenido y plantillas
│   ├── utils.py           # Utilidades diversas
│   └── main.py            # Script principal ejecutable
├── tests/
│   ├── test_config.py     # Tests para módulo de configuración
│   ├── test_database.py   # Tests para módulo de base de datos
│   ├── test_api.py        # Tests para módulo de API
│   └── test_content_processor.py # Tests para procesador de contenido
├── templates/
│   └── post_template.j2   # Ejemplo de plantilla Jinja2
├── Dockerfile             # Configuración para Docker
├── requirements.txt       # Dependencias del proyecto
└── README.md              # Este archivo
```

## Requisitos

- Python 3.9 o superior
- Dependencias listadas en `requirements.txt`:
  - requests
  - feedparser
  - beautifulsoup4
  - colorama
  - tqdm
  - Jinja2
  - Pillow
  - piexif
  - pytest (para tests)

## Instalación

### Método 1: Instalación local

1. Clone el repositorio:
   ```bash
   git clone https://github.com/usuario/wp_importer_project.git
   cd wp_importer_project
   ```

2. Cree un entorno virtual y actívelo:
   ```bash
   python -m venv venv
   # En Linux/Mac:
   source venv/bin/activate
   # En Windows:
   venv\Scripts\activate
   ```

3. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

### Método 2: Instalación con Docker

1. Clone el repositorio.

2. Construya la imagen Docker:
   ```bash
   docker build -t wp_importer .
   ```

## Configuración

### Variables de entorno
El importador puede configurarse mediante variables de entorno:

- `WP_API_URL`: URL base de la API REST de WordPress (ej: "https://misitio.com/wp-json/wp/v2")
- `WP_USER`: Nombre de usuario para WordPress
- `WP_PASS`: Contraseña o token de aplicación para WordPress
- `WP_FEED_URL`: URL del feed RSS a importar (opcional)

### Archivo de configuración
Alternativamente, puede crear un archivo JSON de configuración:

```json
{
  "WP_URL": "https://misitio.com/wp-json/wp/v2",
  "WP_USER": "admin",
  "WP_PASS": "tu_contraseña",
  "FEED_URL": "https://otro-sitio.com/feed/",
  "MAX_POSTS": 10,
  "IMPORT_IMAGENES": true,
  "MODO_ASINCRONO": true,
  "MAX_WORKERS": 3
}
```

## Uso

### Modo CLI

El importador puede ejecutarse desde línea de comandos con varias opciones:

```bash
# Modo básico (carga configuración desde archivo config_importador.json)
python wp_importer/main.py

# Especificar un archivo de configuración
python wp_importer/main.py --config mi_config.json

# Importar específicamente un tipo de contenido
python wp_importer/main.py --tipo posts
python wp_importer/main.py --tipo paginas
python wp_importer/main.py --tipo productos

# Utilizar una plantilla Jinja2 personalizada
python wp_importer/main.py --template templates/mi_plantilla.j2

# Ejecutar en modo automático (sin interacción)
python wp_importer/main.py --modo automatico
```

### Modo Docker

```bash
# Ejecución básica
docker run -it --rm wp_importer

# Con variables de entorno
docker run -it --rm \
  -e WP_API_URL="https://misitio.com/wp-json/wp/v2" \
  -e WP_USER="admin" \
  -e WP_PASS="contraseña" \
  wp_importer

# Montando volumen para archivos de configuración
docker run -it --rm \
  -v $(pwd)/config:/app/config \
  wp_importer --config /app/config/mi_config.json
```

## Modo interactivo

El programa ofrece un menú interactivo con las siguientes opciones:

1. **Probar extracción de feed**: Lee el feed y muestra las entradas sin modificar WordPress.
2. **Ejecutar proceso completo**: Importa contenido a WordPress según configuración.
3. **Configurar opciones avanzadas**: Permite modificar parámetros de la importación.
4. **Ver estadísticas de importación**: Muestra resumen de importaciones realizadas.
5. **Exportar estadísticas a CSV/JSON**: Genera archivos de reportes.
6. **Guardar/cargar configuración**: Gestiona archivos de configuración.

## Configuración para WordPress

### API REST de WordPress

1. Asegúrese de que la API REST está habilitada en su sitio (normalmente lo está por defecto).
2. Para autenticación, puede usar:
   - Usuario y contraseña normal (menos seguro, solo para pruebas)
   - Token de Aplicación (recomendado para producción):
     1. En WordPress, vaya a Usuarios → Perfil → Contraseñas de aplicación
     2. Genere una nueva contraseña para "WP Importer"
     3. Use esta contraseña en el campo `WP_PASS`

### Para productos WooCommerce

1. Asegúrese de tener WooCommerce instalado y activado.
2. Para usar la API de WooCommerce, necesitará:
   - Claves API de WooCommerce (en WooCommerce → Ajustes → Avanzado → API REST)
   - Crear categorías de productos previamente

## Características Avanzadas

### Sistema de Plantillas Jinja2

Puede personalizar el formato del contenido importado utilizando plantillas Jinja2. Ejemplo:

```jinja
<article class="post-importado">
  <h1>{{ titulo }}</h1>
  
  <div class="meta">
    {% if fecha %}
    <span class="fecha">{{ fecha }}</span>
    {% endif %}
    {% if autor %}
    <span class="autor">Por: {{ autor }}</span>
    {% endif %}
  </div>
  
  <div class="contenido">
    {{ contenido }}
  </div>
  
  {% if categorias %}
  <div class="categorias">
    Categorías: 
    {% for categoria in categorias %}
      <span class="categoria">{{ categoria }}</span>
    {% endfor %}
  </div>
  {% endif %}
</article>
```

### Optimización de Imágenes

El importador puede procesar automáticamente las imágenes encontradas en el contenido:

- Redimensiona imágenes grandes
- Comprime manteniendo calidad aceptable
- Extrae metadatos EXIF (geolocalización, fecha de captura, etc.)
- Corrige rotación basada en orientación EXIF

### Rotación de Proxies

Para distribuir las peticiones a través de diferentes IPs:

1. Configure una lista de proxies en el archivo de configuración:
   ```json
   {
     "PROXIES": [
       "http://proxy1.ejemplo.com:8080",
       "http://usuario:contraseña@proxy2.ejemplo.com:8080"
     ]
   }
   ```
2. El sistema rotará automáticamente entre estos proxies para las peticiones.

### Detección de Cambios

Para posts ya importados, el sistema puede detectar si el contenido ha cambiado y actualizarlo:

```json
{
  "AUTO_DETECTAR_CAMBIOS": true
}
```

## Pruebas Unitarias

Para ejecutar las pruebas unitarias:

```bash
pytest tests/
```

O para un módulo específico:

```bash
pytest tests/test_api.py
```

## Integración con Tareas Programadas (Cron)

### Linux/Mac (crontab)

Ejemplo para ejecutar la importación diariamente a las 2 AM:

```
0 2 * * * cd /ruta/al/proyecto && /ruta/al/python wp_importer/main.py --modo automatico >> /ruta/logs/importacion.log 2>&1
```

### Windows (Programador de tareas)

1. Cree un archivo .bat con el comando:
   ```batch
   @echo off
   cd C:\ruta\al\proyecto
   C:\ruta\a\python.exe wp_importer\main.py --modo automatico
   ```
2. Programe este archivo .bat usando el Programador de tareas de Windows.

## Seguridad

### Manejo de Credenciales

- Las credenciales nunca se almacenan en texto plano en el código
- Se recomienda usar variables de entorno o archivos .env
- Para mayor seguridad, use tokens de aplicación en lugar de contraseñas

### Prevención de Inyección SQL

- Todas las consultas a la base de datos utilizan consultas parametrizadas
- Los datos de entrada siempre se validan antes de procesarse

### Sanitización de HTML

El contenido HTML importado se sanitiza para eliminar scripts maliciosos y otros elementos potencialmente peligrosos.

## Solución de Problemas

### Mensajes de Error Comunes

- **"Error en get_with_retry"**: Problema de conexión. Verifique su conexión a internet o pruebe con otro proxy.
- **"La configuración no se pudo validar"**: Credenciales incorrectas o URL de WordPress mal formada.
- **"Error subiendo imagen"**: Problema al procesar o subir imagen. Verifique permisos de WordPress.

### Logs

Los logs se guardan en archivos con formato `wp_importer_YYYYMMDD_HHMMSS.log` y contienen información detallada sobre la ejecución.

## Contribución

Las contribuciones son bienvenidas. Para contribuir:

1. Haga un fork del repositorio
2. Cree una rama para su característica (`git checkout -b feature/nueva-caracteristica`)
3. Implemente sus cambios y pruebas
4. Envíe un pull request

## Licencia

Este proyecto está licenciado bajo MIT License.

## Agradecimientos

- Equipo de WordPress por la API REST
- Comunidad de Python por las excelentes librerías utilizadas
