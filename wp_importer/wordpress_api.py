"""
Módulo para interactuar con la API REST de WordPress y WooCommerce.

Contiene funciones para:
- Crear/actualizar posts y páginas.
- Crear/actualizar productos WooCommerce (incluye metadatos: precio, inventario, categorías).
- Subir imágenes y asignarlas como destacadas.
- Soporte para rotación de proxies.
"""

import requests
import json
import time
import os
import logging
from wp_importer.database import log_in_file_and_db
from colorama import Fore


def get_with_retry(url, headers=None, timeout=15, max_attempts=3, delay=2, backoff=2, manager=None, proxies=None):
    """
    Realiza peticiones GET con reintentos y backoff exponencial.
    Permite configurar proxies para la rotación de IPs.

    Args:
        url: URL para realizar la petición GET
        headers: Cabeceras HTTP (opcional)
        timeout: Tiempo máximo de espera en segundos
        max_attempts: Número máximo de intentos
        delay: Retraso inicial entre intentos (segundos)
        backoff: Factor de incremento del retraso
        manager: Instancia de WPConfigManager para logging (opcional)
        proxies: Configuración de proxies (opcional)

    Returns:
        Response: Objeto de respuesta de requests

    Raises:
        Exception: Si todos los intentos fallan
    """
    attempt = 0
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                          "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    while attempt < max_attempts:
        try:
            response = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
            response.raise_for_status()
            return response
        except Exception as e:
            attempt += 1
            if manager:
                log_in_file_and_db(manager, "ERROR",
                                   f"Error en get_with_retry para {url} (intento {attempt}/{max_attempts}): {e}")
            else:
                logging.error(f"Error en get_with_retry para {url} (intento {attempt}/{max_attempts}): {e}")

            if attempt < max_attempts:
                time.sleep(delay)
                delay *= backoff

    raise Exception(f"Falló GET para {url} después de {max_attempts} intentos")


def post_with_retry(url, data=None, json_data=None, headers=None, auth=None, timeout=15,
                    max_attempts=3, delay=2, backoff=2, manager=None, proxies=None):
    """
    Realiza peticiones POST con reintentos y backoff exponencial.
    Permite configurar proxies para la rotación de IPs.

    Args:
        url: URL para realizar la petición POST
        data: Datos para el POST (form-data)
        json_data: Datos para el POST (JSON)
        headers: Cabeceras HTTP (opcional)
        auth: Autenticación (usuario, contraseña)
        timeout: Tiempo máximo de espera en segundos
        max_attempts: Número máximo de intentos
        delay: Retraso inicial entre intentos (segundos)
        backoff: Factor de incremento del retraso
        manager: Instancia de WPConfigManager para logging (opcional)
        proxies: Configuración de proxies (opcional)

    Returns:
        Response: Objeto de respuesta de requests

    Raises:
        Exception: Si todos los intentos fallan
    """
    attempt = 0
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                          "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    while attempt < max_attempts:
        try:
            response = requests.post(url, data=data, json=json_data, headers=headers,
                                     auth=auth, timeout=timeout, proxies=proxies)
            response.raise_for_status()
            return response
        except Exception as e:
            attempt += 1
            if manager:
                log_in_file_and_db(manager, "ERROR",
                                   f"Error en post_with_retry para {url} (intento {attempt}/{max_attempts}): {e}")
            else:
                logging.error(f"Error en post_with_retry para {url} (intento {attempt}/{max_attempts}): {e}")

            if attempt < max_attempts:
                time.sleep(delay)
                delay *= backoff

    raise Exception(f"Falló POST para {url} después de {max_attempts} intentos")


def validar_configuracion(wp_url, wp_user, wp_pass, manager=None):
    """
    Valida la configuración de WordPress probando el endpoint /users/me.

    Args:
        wp_url: URL base de la API REST de WordPress
        wp_user: Nombre de usuario
        wp_pass: Contraseña o token de aplicación
        manager: Instancia de WPConfigManager para logging (opcional)

    Returns:
        bool: True si la configuración es válida, False en caso contrario
    """
    # Asegurarnos de que la URL termina con /wp-json/wp/v2
    if not wp_url.endswith('/wp-json/wp/v2'):
        wp_url = wp_url.rstrip('/') + '/wp-json/wp/v2'

    url = f"{wp_url}/users/me"
    try:
        response = requests.get(url, auth=(wp_user, wp_pass), timeout=15)
        response.raise_for_status()
        log_msg = f"Configuración válida para {wp_url}"
        if manager:
            log_in_file_and_db(manager, "INFO", log_msg)
        else:
            logging.info(log_msg)
        return True
    except requests.exceptions.RequestException as e:
        log_msg = f"Error validando configuración para {wp_url}: {e}"
        if manager:
            log_in_file_and_db(manager, "ERROR", log_msg)
        else:
            logging.error(log_msg)
        return False


#########################################
# Funciones para crear o actualizar posts
#########################################

def create_or_update_post(titulo, contenido, slug, wp_url, auth, featured_media_id=None, proxy_manager=None):
    """
    Crea o actualiza un post regular en WordPress.

    Args:
        titulo: Título del post
        contenido: Contenido HTML del post
        slug: Slug para la URL
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        featured_media_id: ID de la imagen destacada (opcional)
        proxy_manager: Instancia de ProxyManager para usar proxies (opcional)

    Returns:
        dict: Datos del post creado/actualizado, o None si falló
    """
    endpoint = wp_url.rstrip("/") + "/posts"
    payload = {
        "title": titulo,
        "content": contenido,
        "slug": slug,
        "status": "publish"
    }

    # Agregar imagen destacada si se proporciona
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    # Obtener proxy si se proporciona un gestor
    proxies = proxy_manager.get_next_proxy() if proxy_manager else None

    try:
        # Primero intentamos crear el post
        response = post_with_retry(endpoint, json_data=payload, auth=auth, proxies=proxies)
        print(Fore.GREEN + f"Post '{titulo}' creado con éxito (ID: {response.json().get('id')}).")
        return response.json()
    except requests.exceptions.HTTPError as err:
        # Si ya existe (por ejemplo, se detecta conflicto de slug), se actualiza
        response = err.response
        if response.status_code == 409:
            # Buscar el post por slug y luego actualizarlo
            post = buscar_post_por_slug(slug, wp_url, auth, proxies)
            if post:
                post_id = post.get("id")
                endpoint_update = wp_url.rstrip("/") + f"/posts/{post_id}"
                response = post_with_retry(endpoint_update, json_data=payload, auth=auth, proxies=proxies)
                print(Fore.YELLOW + f"Post '{titulo}' actualizado (ID: {post_id}).")
                return response.json()
        print(Fore.RED + f"Error creando post '{titulo}': {err}")
        return None
    except Exception as e:
        print(Fore.RED + f"Error inesperado creando post '{titulo}': {e}")
        logging.error(f"Error inesperado creando post '{titulo}': {e}")
        return None


def buscar_post_por_slug(slug, wp_url, auth, proxies=None):
    """
    Busca un post en WordPress por su slug.

    Args:
        slug: Slug del post a buscar
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        proxies: Configuración de proxies (opcional)

    Returns:
        dict: Datos del post, o None si no se encuentra
    """
    endpoint = wp_url.rstrip("/") + f"/posts?slug={slug}"
    try:
        response = get_with_retry(endpoint, auth=auth, proxies=proxies)
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        logging.error(f"Error buscando post por slug '{slug}': {e}")
        return None


#########################################
# Funciones para crear o actualizar páginas
#########################################

def create_or_update_page(titulo, contenido, slug, wp_url, auth, featured_media_id=None, proxy_manager=None):
    """
    Crea o actualiza una página en WordPress.

    Args:
        titulo: Título de la página
        contenido: Contenido HTML de la página
        slug: Slug para la URL
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        featured_media_id: ID de la imagen destacada (opcional)
        proxy_manager: Instancia de ProxyManager para usar proxies (opcional)

    Returns:
        dict: Datos de la página creada/actualizada, o None si falló
    """
    endpoint = wp_url.rstrip("/") + "/pages"
    payload = {
        "title": titulo,
        "content": contenido,
        "slug": slug,
        "status": "publish"
    }

    # Agregar imagen destacada si se proporciona
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    # Obtener proxy si se proporciona un gestor
    proxies = proxy_manager.get_next_proxy() if proxy_manager else None

    try:
        # Primero intentamos crear la página
        response = post_with_retry(endpoint, json_data=payload, auth=auth, proxies=proxies)
        print(Fore.GREEN + f"Página '{titulo}' creada con éxito (ID: {response.json().get('id')}).")
        return response.json()
    except requests.exceptions.HTTPError as err:
        # Si ya existe (por ejemplo, se detecta conflicto de slug), se actualiza
        response = err.response
        if response.status_code == 409:
            # Buscar la página por slug y luego actualizarla
            page = buscar_page_por_slug(slug, wp_url, auth, proxies)
            if page:
                page_id = page.get("id")
                endpoint_update = wp_url.rstrip("/") + f"/pages/{page_id}"
                response = post_with_retry(endpoint_update, json_data=payload, auth=auth, proxies=proxies)
                print(Fore.YELLOW + f"Página '{titulo}' actualizada (ID: {page_id}).")
                return response.json()
        print(Fore.RED + f"Error creando página '{titulo}': {err}")
        return None
    except Exception as e:
        print(Fore.RED + f"Error inesperado creando página '{titulo}': {e}")
        logging.error(f"Error inesperado creando página '{titulo}': {e}")
        return None


def buscar_page_por_slug(slug, wp_url, auth, proxies=None):
    """
    Busca una página por slug.

    Args:
        slug: Slug de la página a buscar
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        proxies: Configuración de proxies (opcional)

    Returns:
        dict: Datos de la página, o None si no se encuentra
    """
    endpoint = wp_url.rstrip("/") + f"/pages?slug={slug}"
    try:
        response = get_with_retry(endpoint, auth=auth, proxies=proxies)
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        logging.error(f"Error buscando página por slug '{slug}': {e}")
        return None


#########################################
# Funciones para crear o actualizar productos WooCommerce
#########################################

def create_or_update_product(titulo, descripcion, slug, precio, inventario, categorias, wp_url, auth,
                             featured_media_id=None, proxy_manager=None):
    """
    Crea o actualiza un producto en WooCommerce.

    Args:
        titulo: Nombre del producto
        descripcion: Descripción HTML del producto
        slug: Slug para la URL
        precio: Precio regular del producto
        inventario: Cantidad en stock
        categorias: Lista de IDs de categorías
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        featured_media_id: ID de la imagen destacada (opcional)
        proxy_manager: Instancia de ProxyManager para usar proxies (opcional)

    Returns:
        dict: Datos del producto creado/actualizado, o None si falló
    """
    # Ajustar endpoint para apuntar a la API de WooCommerce
    # Nota: esto supone que la URL base es /wp-json/wp/v2, así que retrocedemos y usamos /wp-json/wc/v3
    if "/wp/v2" in wp_url:
        base_url = wp_url.split("/wp/v2")[0]
        endpoint = f"{base_url}/wc/v3/products"
    else:
        endpoint = wp_url.rstrip("/") + "/../wc/v3/products"

    # Preparar el payload para la API de WooCommerce
    payload = {
        "name": titulo,
        "description": descripcion,
        "short_description": descripcion[:150] + "..." if len(descripcion) > 150 else descripcion,
        "slug": slug,
        "regular_price": str(precio),
        "manage_stock": True,
        "stock_quantity": inventario,
        "categories": [{"id": cat_id} for cat_id in categorias],
        "status": "publish"
    }

    # Agregar imagen destacada si se proporciona
    if featured_media_id:
        payload["images"] = [{"id": featured_media_id}]

    # Obtener proxy si se proporciona un gestor
    proxies = proxy_manager.get_next_proxy() if proxy_manager else None

    try:
        # Primero intentamos crear el producto
        response = post_with_retry(endpoint, json_data=payload, auth=auth, proxies=proxies)
        print(Fore.GREEN + f"Producto '{titulo}' creado con éxito (ID: {response.json().get('id')}).")
        return response.json()
    except requests.exceptions.HTTPError as err:
        # Si ya existe (por ejemplo, se detecta conflicto de slug), se actualiza
        response = err.response
        if response.status_code == 409:
            # Buscar el producto por slug y luego actualizarlo
            producto = buscar_producto_por_slug(slug, wp_url, auth, proxies)
            if producto:
                prod_id = producto.get("id")
                endpoint_update = f"{endpoint}/{prod_id}"
                response = post_with_retry(endpoint_update, json_data=payload, auth=auth, proxies=proxies)
                print(Fore.YELLOW + f"Producto '{titulo}' actualizado (ID: {prod_id}).")
                return response.json()
        print(Fore.RED + f"Error creando producto '{titulo}': {err}")
        return None
    except Exception as e:
        print(Fore.RED + f"Error inesperado creando producto '{titulo}': {e}")
        logging.error(f"Error inesperado creando producto '{titulo}': {e}")
        return None


def buscar_producto_por_slug(slug, wp_url, auth, proxies=None):
    """
    Busca un producto WooCommerce por slug.

    Args:
        slug: Slug del producto a buscar
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        proxies: Configuración de proxies (opcional)

    Returns:
        dict: Datos del producto, o None si no se encuentra
    """
    # Ajustar endpoint para la API de WooCommerce
    if "/wp/v2" in wp_url:
        base_url = wp_url.split("/wp/v2")[0]
        endpoint = f"{base_url}/wc/v3/products"
    else:
        endpoint = wp_url.rstrip("/") + "/../wc/v3/products"

    search_endpoint = f"{endpoint}?slug={slug}"
    try:
        response = get_with_retry(search_endpoint, auth=auth, proxies=proxies)
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        logging.error(f"Error buscando producto por slug '{slug}': {e}")
        return None


#########################################
# Función para subir imágenes y asignarlas como destacadas
#########################################

def upload_image(image_path, wp_url, auth, proxy_manager=None):
    """
    Sube una imagen a la biblioteca de medios de WordPress.

    Args:
        image_path: Ruta al archivo de imagen local
        wp_url: URL base de la API REST de WordPress
        auth: Tupla (usuario, contraseña) para autenticación
        proxy_manager: Instancia de ProxyManager para usar proxies (opcional)

    Returns:
        int: ID de la imagen subida, o None si falló
    """
    endpoint = wp_url.rstrip("/") + "/media"
    proxies = proxy_manager.get_next_proxy() if proxy_manager else None

    # Preparar cabeceras para la subida de la imagen
    filename = os.path.basename(image_path)
    mime_type = "image/jpeg"  # Por defecto (se podría mejorar detectando el tipo de archivo)
    if filename.endswith('.png'):
        mime_type = "image/png"
    elif filename.endswith('.gif'):
        mime_type = "image/gif"
    elif filename.endswith('.webp'):
        mime_type = "image/webp"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mime_type
    }

    try:
        with open(image_path, "rb") as img:
            response = post_with_retry(endpoint, data=img, headers=headers, auth=auth, proxies=proxies)
            data = response.json()
            image_id = data.get("id")
            print(Fore.GREEN + f"Imagen subida: {filename} (ID: {image_id})")
            return image_id
    except Exception as e:
        print(Fore.RED + f"Error subiendo imagen {image_path}: {e}")
        logging.error(f"Error subiendo imagen {image_path}: {e}")
        return None


#########################################
# Implementación de rotación de proxies
#########################################

class ProxyManager:
    """
    Maneja una lista de proxies para rotar automáticamente en cada solicitud.

    Atributos:
        proxies_list (list): Lista de URLs de proxies
        index (int): Índice actual en la lista de proxies
    """

    def __init__(self, proxies_list):
        """
        Inicializa el gestor de proxies.

        Args:
            proxies_list: Lista de URLs de proxies (formato: "http://ip:puerto")
        """
        self.proxies_list = proxies_list
        self.index = 0
        logging.info(f"ProxyManager inicializado con {len(proxies_list)} proxies.")

    def get_next_proxy(self):
        """
        Obtiene el siguiente proxy de la lista de forma cíclica.

        Returns:
            dict: Diccionario de configuración de proxy para requests, o None si no hay proxies
        """
        if not self.proxies_list:
            return None

        # Obtener el proxy actual
        proxy = self.proxies_list[self.index]

        # Formato para requests: {'http': proxy, 'https': proxy}
        proxy_dict = {"http": proxy, "https": proxy}

        # Avanzar el índice de forma cíclica
        self.index = (self.index + 1) % len(self.proxies_list)

        logging.debug(f"Usando proxy: {proxy}")
        return proxy_dict