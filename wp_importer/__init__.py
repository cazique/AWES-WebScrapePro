"""
Paquete wp_importer - Importador WordPress Optimizado

Un módulo para importar contenido a WordPress desde diversas fuentes,
con soporte para posts, páginas y productos WooCommerce, optimización de imágenes,
sistema de plantillas con Jinja2 y rotación de proxies.

Versión: 2.0.0
Autor: Jorge Martín Casasola
"""

__version__ = '2.0.0'
__author__ = 'Jorge Martín Casasola'

# Importar módulos principales para facilitar su acceso
from wp_importer.config import Config
from wp_importer.database import WPConfigManager, log_in_file_and_db
from wp_importer.wordpress_api import (
    validar_configuracion,
    create_or_update_post,
    create_or_update_page,
    create_or_update_product,
    upload_image,
    ProxyManager
)
from wp_importer.content_processor import (
    render_template,
    optimize_image,
    extract_exif
)
from wp_importer.utils import (
    slugify,
    extract_images_from_html,
    download_image,
    sanitize_html
)