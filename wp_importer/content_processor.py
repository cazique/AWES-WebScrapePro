"""
Módulo para procesar y transformar contenido antes de enviarlo a WordPress.

Proporciona funciones para:
- Renderizar plantillas Jinja2
- Optimizar imágenes (redimensionar, comprimir)
- Extraer metadatos EXIF de imágenes
"""

import os
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ExifTags
import piexif
from colorama import Fore
import io


def render_template(template_path, data):
    """
    Renderiza un template Jinja2 con los datos proporcionados.

    Args:
        template_path: Ruta al archivo de plantilla
        data: Diccionario con datos para renderizar la plantilla

    Returns:
        str: Contenido renderizado
    """
    try:
        template_dir, template_file = os.path.split(template_path)
        env = Environment(
            loader=FileSystemLoader(template_dir or './'),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template(template_file)
        return template.render(data)
    except Exception as e:
        logging.error(f"Error renderizando plantilla {template_path}: {e}")
        print(Fore.RED + f"Error al procesar la plantilla: {e}")
        # En caso de error, devolvemos al menos el contenido original
        return data.get('contenido', '')


def optimize_image(input_path, output_path, max_width=1920, quality=85, preserve_exif=True):
    """
    Optimiza la imagen: redimensiona si es más ancha que max_width y guarda comprimida.

    Args:
        input_path: Ruta de la imagen original
        output_path: Ruta donde guardar la imagen optimizada
        max_width: Ancho máximo permitido para la imagen
        quality: Calidad de compresión (0-100, mayor es mejor calidad)
        preserve_exif: Si se deben preservar los metadatos EXIF

    Returns:
        bool: True si se optimizó correctamente, False en caso contrario
    """
    try:
        exif_data = None

        with Image.open(input_path) as img:
            # Extraer EXIF si es necesario preservarlo
            if preserve_exif:
                try:
                    exif_data = piexif.load(img.info.get('exif', b''))
                except:
                    pass

            # Redimensionar si es necesario
            width, height = img.size
            if width > max_width:
                new_height = int((max_width / width) * height)
                img = img.resize((max_width, new_height), Image.LANCZOS)

            # Si es un archivo JPEG, optimizamos al guardar
            format_to_save = img.format if img.format else 'JPEG'

            # Guardar la imagen optimizada
            save_params = {
                'format': format_to_save,
                'optimize': True,
                'quality': quality
            }

            # Incluir EXIF si está disponible y se debe preservar
            if preserve_exif and exif_data and format_to_save == 'JPEG':
                exif_bytes = piexif.dump(exif_data)
                save_params['exif'] = exif_bytes

            img.save(output_path, **save_params)

        # Calcular el ahorro de tamaño
        original_size = os.path.getsize(input_path)
        optimized_size = os.path.getsize(output_path)
        saving_percent = 100 - (optimized_size / original_size * 100)

        print(Fore.GREEN + f"Imagen optimizada: {input_path} -> {output_path}")
        print(
            Fore.GREEN + f"Reducción de tamaño: {saving_percent:.1f}% ({original_size / 1024:.1f}KB -> {optimized_size / 1024:.1f}KB)")

        return True
    except Exception as e:
        logging.error(f"Error optimizando imagen {input_path}: {e}")
        print(Fore.RED + f"Error optimizando imagen: {e}")
        # Si hay error, intentamos al menos copiar el archivo original
        try:
            if input_path != output_path:  # Solo si son diferentes rutas
                import shutil
                shutil.copy(input_path, output_path)
                return True
        except:
            pass
        return False


def extract_exif(input_path):
    """
    Extrae metadatos EXIF de la imagen.

    Args:
        input_path: Ruta de la imagen

    Returns:
        dict: Diccionario con los metadatos EXIF
    """
    try:
        exif_data = {}
        with Image.open(input_path) as img:
            # Intentar obtener los datos EXIF
            raw_exif = img._getexif()
            if raw_exif:
                # Convertir las etiquetas numéricas a nombres legibles
                for tag, value in raw_exif.items():
                    if tag in ExifTags.TAGS:
                        tag_name = ExifTags.TAGS[tag]
                        # Convertir algunos valores a formatos más legibles
                        if tag_name == 'GPSInfo' and value:
                            gps_info = {}
                            for gps_tag, gps_value in value.items():
                                if gps_tag in ExifTags.GPSTAGS:
                                    gps_info[ExifTags.GPSTAGS[gps_tag]] = gps_value
                            exif_data[tag_name] = gps_info
                        else:
                            # Convertir bytes y otros tipos complejos a strings
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode('utf-8')
                                except:
                                    value = str(value)
                            exif_data[tag_name] = value

        return exif_data
    except Exception as e:
        logging.error(f"Error extrayendo EXIF de {input_path}: {e}")
        return {}


def rotate_image_by_exif(input_path, output_path=None):
    """
    Rota una imagen según la orientación EXIF.

    Args:
        input_path: Ruta de la imagen original
        output_path: Ruta donde guardar la imagen rotada (si None, sobreescribe la original)

    Returns:
        bool: True si se rotó correctamente, False en caso contrario
    """
    if output_path is None:
        output_path = input_path

    try:
        with Image.open(input_path) as img:
            # Extraer orientación EXIF
            exif_data = img._getexif()
            if exif_data is None:
                return False

            # La etiqueta de orientación en EXIF es 274
            orientation = exif_data.get(274, 1)

            # Aplicar rotación según orientación
            if orientation == 1:
                # No se requiere rotación
                return False
            elif orientation == 2:
                # Reflejo horizontal
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                # Rotación 180°
                img = img.transpose(Image.ROTATE_180)
            elif orientation == 4:
                # Reflejo vertical
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                # Reflejo horizontal + rotación 90° CCW
                img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
            elif orientation == 6:
                # Rotación 90° CW
                img = img.transpose(Image.ROTATE_270)
            elif orientation == 7:
                # Reflejo horizontal + rotación 270° CW
                img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
            elif orientation == 8:
                # Rotación 270° CW
                img = img.transpose(Image.ROTATE_90)

            # Guardar imagen rotada (eliminando el tag de orientación)
            if 'exif' in img.info:
                exif_dict = piexif.load(img.info['exif'])
                if '0th' in exif_dict and 274 in exif_dict['0th']:
                    # Cambiar orientación a normal (1)
                    exif_dict['0th'][274] = 1
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(output_path, exif=exif_bytes)
                else:
                    img.save(output_path)
            else:
                img.save(output_path)

            return True
    except Exception as e:
        logging.error(f"Error rotando imagen {input_path}: {e}")
        return False


def is_image_url(url):
    """
    Verifica si una URL corresponde a una imagen basándose en la extensión.

    Args:
        url: URL a verificar

    Returns:
        bool: True si parece ser una imagen, False en caso contrario
    """
    # Extensiones comunes de imágenes
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']

    # Verificar si la URL termina con alguna de estas extensiones
    return any(url.lower().endswith(ext) for ext in image_extensions)