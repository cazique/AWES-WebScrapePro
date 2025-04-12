"""
Módulo de utilidades para el importador WordPress.

Contiene funciones auxiliares como:
- Conversión de texto a slugs
- Extracción de imágenes de contenido HTML
- Descarga de imágenes
"""

import re
import unicodedata
import os
import logging
import requests
import tempfile
from bs4 import BeautifulSoup
from colorama import Fore
import uuid

def slugify(text):
    """
    Convierte un texto en un slug URL-friendly.
    
    Args:
        text: Texto a convertir
        
    Returns:
        str: Slug generado
    """
    # Normalizar texto (eliminar acentos)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Convertir a minúsculas
    text = text.lower()
    # Eliminar caracteres no alfanuméricos
    text = re.sub(r'[^\w\s-]', '', text)
    # Reemplazar espacios y guiones bajos por guiones
    text = re.sub(r'[-\s_]+', '-', text)
    # Eliminar guiones al principio y final
    text = text.strip('-')
    return text

def extract_images_from_html(html_content):
    """
    Extrae URLs de imágenes de contenido HTML.
    
    Args:
        html_content: Contenido HTML
        
    Returns:
        list: Lista de URLs de imágenes
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        image_urls = []
        
        # Buscar todas las etiquetas <img>
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                image_urls.append(src)
                
        # Buscar imágenes en estilos CSS (background-image)
        style_tags = soup.find_all(['style', lambda tag: tag.has_attr('style')])
        for tag in style_tags:
            # Si es una etiqueta style, buscamos en su contenido
            if tag.name == 'style':
                css_content = tag.string
                if css_content:
                    urls = re.findall(r'url\(["\']?(.*?)["\']?\)', css_content)
                    image_urls.extend(urls)
            # Si es otro elemento con atributo style, buscamos en ese atributo
            elif tag.has_attr('style'):
                style_attr = tag['style']
                urls = re.findall(r'url\(["\']?(.*?)["\']?\)', style_attr)
                image_urls.extend(urls)
        
        # Eliminar duplicados y URLs vacías
        image_urls = list(filter(None, set(image_urls)))
        
        return image_urls
    except Exception as e:
        logging.error(f"Error extrayendo imágenes del HTML: {e}")
        return []

def download_image(url, proxy_manager=None, max_retries=3):
    """
    Descarga una imagen desde una URL.
    
    Args:
        url: URL de la imagen
        proxy_manager: Gestor de proxies (opcional)
        max_retries: Número máximo de intentos
        
    Returns:
        str: Ruta del archivo temporal con la imagen descargada, o None si falló
    """
    for attempt in range(max_retries):
        try:
            proxies = proxy_manager.get_next_proxy() if proxy_manager else None
            
            # Crear una sesión para usar proxies
            session = requests.Session()
            if proxies:
                session.proxies.update(proxies)
            
            # Establecer un tiempo de espera razonable
            response = session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Verificar que el contenido es una imagen
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logging.warning(f"La URL no es una imagen: {url} (Content-Type: {content_type})")
                return None
            
            # Generar un nombre de archivo temporal único
            temp_dir = tempfile.gettempdir()
            file_extension = os.path.splitext(url)[1]
            if not file_extension:
                # Intentar determinar la extensión desde el Content-Type
                content_type_map = {
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/webp': '.webp',
                    'image/bmp': '.bmp',
                    'image/tiff': '.tiff'
                }
                file_extension = content_type_map.get(content_type, '.jpg')
            
            # Asegurarnos de que la extensión empieza con punto
            if not file_extension.startswith('.'):
                file_extension = '.' + file_extension
            
            temp_file = os.path.join(temp_dir, f"wp_import_{uuid.uuid4().hex}{file_extension}")
            
            # Guardar la imagen
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(Fore.GREEN + f"Imagen descargada: {url} -> {temp_file}")
            return temp_file
        
        except Exception as e:
            logging.error(f"Error descargando imagen {url} (intento {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                print(Fore.RED + f"No se pudo descargar la imagen: {url}")
                return None
    
    return None

def sanitize_html(html_content, allowed_tags=None):
    """
    Sanitiza contenido HTML eliminando scripts y otros elementos potencialmente peligrosos.
    
    Args:
        html_content: Contenido HTML a sanitizar
        allowed_tags: Lista de etiquetas permitidas (si None, se usa una lista predeterminada)
        
    Returns:
        str: Contenido HTML sanitizado
    """
    if allowed_tags is None:
        allowed_tags = [
            'a', 'abbr', 'acronym', 'address', 'area', 'article', 'aside',
            'audio', 'b', 'big', 'blockquote', 'br', 'button', 'canvas',
            'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'data',
            'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'div', 'dl',
            'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'footer',
            'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hgroup',
            'hr', 'i', 'img', 'input', 'ins', 'kbd', 'keygen', 'label',
            'legend', 'li', 'map', 'mark', 'menu', 'menuitem', 'meter', 'nav',
            'noscript', 'object', 'ol', 'optgroup', 'option', 'output', 'p',
            'param', 'picture', 'pre', 'progress', 'q', 'rp', 'rt', 'ruby',
            's', 'samp', 'section', 'select', 'small', 'source', 'span',
            'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td',
            'textarea', 'tfoot', 'th', 'thead', 'time', 'tr', 'track', 'u',
            'ul', 'var', 'video', 'wbr'
        ]
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Eliminar comentarios
        for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
        
        # Eliminar etiquetas no permitidas
        for tag in soup.find_all():
            if tag.name not in allowed_tags:
                tag.unwrap()  # Mantener el contenido pero eliminar la etiqueta
        
        # Eliminar atributos potencialmente peligrosos
        dangerous_attrs = ['onload', 'onerror', 'onclick', 'onmouseover', 'onmouseout',
                         'onkeydown', 'onkeypress', 'onkeyup', 'onchange', 'onsubmit']
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                # Eliminar atributos peligrosos o que comiencen con "on"
                if attr in dangerous_attrs or attr.startswith('on'):
                    del tag[attr]
                # Limpiar URLs en href y src
                elif attr in ['href', 'src'] and tag[attr]:
                    if tag[attr].startswith('javascript:'):
                        del tag[attr]
        
        return str(soup)
    
    except Exception as e:
        logging.error(f"Error sanitizando HTML: {e}")
        # En caso de error, simplemente eliminar las etiquetas script
        return re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content)

def get_human_readable_size(size_bytes):
    """
    Convierte un tamaño en bytes a una representación legible por humanos.
    
    Args:
        size_bytes: Tamaño en bytes
        
    Returns:
        str: Tamaño en formato legible (KB, MB, GB)
    """
    if size_bytes < 0:
        raise ValueError("El tamaño no puede ser negativo")
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"

def create_directory_if_not_exists(directory):
    """
    Crea un directorio si no existe.
    
    Args:
        directory: Ruta del directorio a crear
        
    Returns:
        bool: True si se creó correctamente o ya existía, False en caso contrario
    """
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logging.info(f"Directorio creado: {directory}")
        return True
    except Exception as e:
        logging.error(f"Error creando directorio {directory}: {e}")
        return False

def safe_filename(filename):
    """
    Convierte un nombre de archivo en uno seguro para el sistema de archivos.
    
    Args:
        filename: Nombre de archivo original
        
    Returns:
        str: Nombre de archivo seguro
    """
    # Caracteres no permitidos en nombres de archivo
    invalid_chars = r'[<>:"/\\|?*]'
    # Reemplazar caracteres no permitidos por guion bajo
    safe_name = re.sub(invalid_chars, '_', filename)
    # Limitar longitud a 200 caracteres para evitar problemas en algunos sistemas
    if len(safe_name) > 200:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:200-len(ext)] + ext
    return safe_name