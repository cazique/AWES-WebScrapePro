#!/usr/bin/env python3
"""
Main del importador WordPress optimizado.

Este script procesa un feed RSS y, según el parámetro de tipo de contenido,
llama a las funciones correspondientes para crear/actualizar posts, páginas o productos WooCommerce.
Incluye ejecución asíncrona con ThreadPoolExecutor, exportación de estadísticas a CSV/JSON,
y uso interactivo para seleccionar o agregar configuraciones.
"""

import argparse
import sys
import feedparser
import os
import csv
import json
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore
from bs4 import BeautifulSoup
import re

# Importamos módulos internos
from wp_importer.config import Config
from wp_importer.database import WPConfigManager, log_in_file_and_db
from wp_importer.wordpress_api import (
    validar_configuracion,
    create_or_update_post,
    create_or_update_page,
    create_or_update_product,
    upload_image,
    get_with_retry,
    ProxyManager
)
from wp_importer.content_processor import render_template, optimize_image, extract_exif
from wp_importer.utils import slugify, download_image, extract_images_from_html

init(autoreset=True)  # Inicializa colorama

def setup_logging():
    """Configura el sistema de logging para el importador."""
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    log_file = f"wp_importer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return log_file

def mostrar_banner():
    """Muestra un banner decorativo para la aplicación."""
    banner = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════╗
{Fore.CYAN}║           IMPORTADOR WORDPRESS OPTIMIZADO - Versión 2.0           ║
{Fore.CYAN}║     Soporta posts, páginas y productos WooCommerce con metadatos  ║
{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)

def mostrar_menu():
    """Muestra el menú principal de la aplicación."""
    print(Fore.CYAN + "\n=== MENÚ PRINCIPAL ===")
    print(Fore.YELLOW + "1. Probar extracción de feed (solo lectura)")
    print(Fore.YELLOW + "2. Ejecutar proceso completo (subir a WordPress)")
    print(Fore.YELLOW + "3. Configurar opciones avanzadas")
    print(Fore.YELLOW + "4. Ver estadísticas de importación")
    print(Fore.YELLOW + "5. Exportar estadísticas a CSV/JSON")
    print(Fore.YELLOW + "6. Guardar/cargar configuración")
    print(Fore.RED + "7. Salir")
    return input(Fore.GREEN + "\nSelecciona una opción: ")

def seleccionar_configuracion(manager):
    """
    Función interactiva para seleccionar o agregar una configuración de WordPress.
    Se intenta primero obtener datos desde las variables de entorno.
    Si no existen, se muestran las configuraciones existentes y se permite elegir
    o añadir una nueva.

    Args:
        manager: Instancia de WPConfigManager para interactuar con la BD

    Returns:
        tuple: (config, wp_config_id) donde config es la configuración y wp_config_id su ID
    """
    configs = manager.list_configurations()

    # Intentar usar variables de entorno
    env_wp_url = os.getenv("WP_API_URL")
    env_wp_user = os.getenv("WP_USER")
    env_wp_pass = os.getenv("WP_PASS")
    env_site_name = os.getenv("WP_SITE_NAME", "Sitio desde variables de entorno")

    if env_wp_url and env_wp_user and env_wp_pass:
        print(Fore.CYAN + "Usando configuración desde variables de entorno.")
        if validar_configuracion(env_wp_url, env_wp_user, env_wp_pass, manager):
            config_id = manager.add_configuration(env_wp_url, env_wp_user, env_wp_pass, env_site_name)
            return manager.get_configuration_by_id(config_id), config_id
        else:
            print(Fore.RED + "Las credenciales definidas en variables de entorno no son válidas.")

    # Si no hay configuraciones guardadas
    if not configs:
        print(Fore.RED + "No hay configuraciones registradas. Por favor, añade una:")
        while True:
            wp_url = input(Fore.YELLOW + "URL de WordPress (ej: https://tusitio.com/wp-json/wp/v2): ").strip()
            wp_user = input(Fore.YELLOW + "Usuario de WordPress: ").strip()
            wp_pass = input(Fore.YELLOW + "Contraseña o Token de aplicación: ").strip()
            site_name = input(Fore.YELLOW + "Nombre descriptivo del sitio (opcional): ").strip()
            if validar_configuracion(wp_url, wp_user, wp_pass, manager):
                config_id = manager.add_configuration(wp_url, wp_user, wp_pass, site_name)
                config = manager.get_configuration_by_id(config_id)
                break
            else:
                print(Fore.RED + "La configuración no se pudo validar. Revisa e intenta de nuevo.")
        return config, config_id
    else:
        # Mostrar lista de configuraciones existentes
        while True:
            print(Fore.CYAN + "\n=== Configuraciones existentes ===")
            for cfg in configs:
                site_name = f" - {cfg[3]}" if cfg[3] else ""
                last_used = f" (Último uso: {cfg[4]})" if cfg[4] else ""
                print(Fore.YELLOW + f"[{cfg[0]}] URL: {cfg[1]}, Usuario: {cfg[2]}{site_name}{last_used}")
            print(Fore.YELLOW + "[N] Añadir nueva configuración")
            print(Fore.YELLOW + "[D] Eliminar configuración")
            selected = input(Fore.GREEN + "Selecciona el ID, 'N' para nueva o 'D' para eliminar: ").strip()

            if selected.upper() == 'N':
                # Agregar nueva configuración
                while True:
                    wp_url = input(Fore.YELLOW + "URL de WordPress: ").strip()
                    wp_user = input(Fore.YELLOW + "Usuario de WordPress: ").strip()
                    wp_pass = input(Fore.YELLOW + "Contraseña o Token: ").strip()
                    site_name = input(Fore.YELLOW + "Nombre del sitio (opcional): ").strip()
                    if validar_configuracion(wp_url, wp_user, wp_pass, manager):
                        config_id = manager.add_configuration(wp_url, wp_user, wp_pass, site_name)
                        config = manager.get_configuration_by_id(config_id)
                        break
                    else:
                        print(Fore.RED + "La configuración no se validó. Revisa e intenta nuevamente.")
                return config, config_id

            elif selected.upper() == 'D':
                # Eliminar configuración existente
                del_id = input(Fore.RED + "Ingrese el ID a eliminar: ").strip()
                if del_id.isdigit() and manager.delete_configuration(int(del_id)):
                    print(Fore.GREEN + "Configuración eliminada.")
                    configs = manager.list_configurations()
                    if not configs:
                        print(Fore.RED + "No quedan configuraciones. Añade una nueva.")
                        continue
                else:
                    print(Fore.RED + "ID inválido o fallo al eliminar.")

            elif selected.isdigit():
                # Seleccionar configuración existente
                config_id = int(selected)
                config = manager.get_configuration_by_id(config_id)
                if config:
                    if validar_configuracion(config[1], config[2], config[3], manager):
                        return config, config_id
                    else:
                        print(Fore.RED + "La configuración seleccionada no es válida.")
                else:
                    print(Fore.RED + "ID no encontrado.")

            else:
                print(Fore.RED + "Opción no válida.")

def exportar_estadisticas(manager, filename_csv=None, filename_json=None):
    """
    Exporta las estadísticas de importación a archivos CSV y JSON.

    Args:
        manager: Instancia de WPConfigManager
        filename_csv: Nombre del archivo CSV de salida (opcional)
        filename_json: Nombre del archivo JSON de salida (opcional)
    """
    if not filename_csv:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_csv = f"estadisticas_importacion_{timestamp}.csv"

    if not filename_json:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_json = f"estadisticas_importacion_{timestamp}.json"

    # Obtener estadísticas
    stats = manager.get_import_statistics()

    # Exportar a CSV
    with open(filename_csv, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Estado", "Cantidad"])
        for status, count in stats:
            writer.writerow([status, count])

    # Exportar a JSON
    stats_dict = {status: count for status, count in stats}
    with open(filename_json, "w", encoding="utf-8") as jsonfile:
        json.dump(stats_dict, jsonfile, indent=4)

    print(Fore.GREEN + f"Estadísticas exportadas a {filename_csv} y {filename_json}")
    return filename_csv, filename_json

def procesar_feed(feed_url, tipo, wp_config, wp_config_id, manager, proxy_manager=None, template_path=None):
    """
    Procesa el feed RSS y, según el tipo (posts, paginas, productos), importa cada entrada.

    Args:
        feed_url: URL del feed RSS a procesar
        tipo: Tipo de contenido a importar ('posts', 'paginas' o 'productos')
        wp_config: Configuración de WordPress
        wp_config_id: ID de la configuración en la base de datos
        manager: Instancia de WPConfigManager
        proxy_manager: ProxyManager para rotación de IPs (opcional)
        template_path: Ruta a la plantilla Jinja2 (opcional)

    Returns:
        list: Resultados de la importación para cada ítem
    """
    print(Fore.GREEN + f"Descargando feed {feed_url}...")

    try:
        # Si hay proxy configurado, lo usamos para obtener el feed
        if proxy_manager:
            proxies = proxy_manager.get_next_proxy()
            response = get_with_retry(feed_url, proxies=proxies, manager=manager)
            feed = feedparser.parse(response.text)
        else:
            feed = feedparser.parse(feed_url)

        if not feed.entries:
            print(Fore.RED + "El feed no contiene entradas o no se pudo procesar correctamente.")
            return []

        # Limitar al número máximo configurado
        items = feed.entries[:Config.MAX_POSTS]
        print(Fore.CYAN + f"Feed leído correctamente. Se procesarán {len(items)} entradas.")

        resultados = []

        # Define la función que procesa un ítem individual
        def procesar_item(item, item_index):
            try:
                # Extraemos campos básicos
                titulo = item.get("title", f"Sin título {item_index}")
                enlace = item.get("link", "")

                # Intentamos obtener el contenido completo, o usamos el resumen si no está disponible
                if hasattr(item, 'content'):
                    contenido_original = item.content[0].value
                else:
                    contenido_original = item.get("summary", "")

                # Generar slug único a partir del título
                slug = slugify(titulo)

                # Aplicar plantilla si se proporciona
                if template_path:
                    # Creamos un diccionario con todos los datos del ítem para la plantilla
                    datos_plantilla = {
                        "titulo": titulo,
                        "contenido": contenido_original,
                        "enlace": enlace,
                        "fecha": item.get("published", ""),
                        "autor": item.get("author", ""),
                        "categorias": [tag.term for tag in item.get("tags", [])] if hasattr(item, "tags") else []
                    }
                    contenido_final = render_template(template_path, datos_plantilla)
                else:
                    contenido_final = contenido_original

                # Verificamos si ya se ha importado este post (por URL)
                post_existente = manager.check_imported_post(wp_config_id, enlace)

                # Si existe y el contenido no ha cambiado, nos saltamos la importación
                if post_existente and not Config.AUTO_DETECTAR_CAMBIOS:
                    print(Fore.YELLOW + f"El ítem '{titulo}' ya fue importado anteriormente (ID: {post_existente[3]}). Omitiendo...")
                    return {"titulo": titulo, "status": "omitido", "post_id": post_existente[3]}

                # Extraer imágenes si está habilitada la importación de imágenes
                imagen_destacada_id = None
                if Config.IMPORT_IMAGENES:
                    # Extraer URLs de imágenes del contenido
                    urls_imagenes = extract_images_from_html(contenido_original)

                    # Limitar a MAX_IMAGENES si está configurado
                    if Config.MAX_IMAGENES > 0:
                        urls_imagenes = urls_imagenes[:Config.MAX_IMAGENES]

                    # Descargar y procesar imágenes
                    for i, url_imagen in enumerate(urls_imagenes):
                        try:
                            # Descargar imagen
                            temp_path = download_image(url_imagen, proxy_manager)
                            if not temp_path:
                                continue

                            # Optimizar imagen si es necesario
                            output_path = f"temp_optimized_{i}.jpg"
                            optimize_image(temp_path, output_path)

                            # Extraer metadatos EXIF si se desea
                            exif_data = extract_exif(output_path)

                            # Subir imagen a WordPress
                            auth = (wp_config[2], wp_config[3])
                            image_id = upload_image(output_path, wp_config[1], auth, proxy_manager)

                            # La primera imagen se usa como destacada
                            if i == 0 and image_id:
                                imagen_destacada_id = image_id

                            # Limpiar archivos temporales
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            if os.path.exists(output_path):
                                os.remove(output_path)

                        except Exception as e:
                            log_in_file_and_db(manager, "ERROR", f"Error procesando imagen {url_imagen}: {str(e)}")

                # Seleccionamos la función según el tipo y publicamos
                auth = (wp_config[2], wp_config[3])

                if tipo == "posts":
                    resultado = create_or_update_post(
                        titulo, contenido_final, slug, wp_config[1], auth,
                        imagen_destacada_id, proxy_manager
                    )
                elif tipo == "paginas":
                    resultado = create_or_update_page(
                        titulo, contenido_final, slug, wp_config[1], auth,
                        imagen_destacada_id, proxy_manager
                    )
                elif tipo == "productos":
                    # Para productos necesitamos metadatos adicionales
                    # Simularemos algunos valores si no están en el feed
                    precio = 19.99  # Valor por defecto
                    inventario = 100  # Valor por defecto
                    categorias = [1]  # Categoría por defecto

                    # Intentar extraer precio del contenido (ejemplo simple)
                    precio_match = re.search(r'precio[:\s]*[$€£]?\s*(\d+[,.]\d+|\d+)', contenido_original, re.IGNORECASE)
                    if precio_match:
                        precio = float(precio_match.group(1).replace(',', '.'))

                    resultado = create_or_update_product(
                        titulo, contenido_final, slug, precio, inventario, categorias,
                        wp_config[1], auth, imagen_destacada_id, proxy_manager
                    )
                else:
                    raise ValueError(f"Tipo de contenido no soportado: {tipo}")

                # Registrar la importación en la base de datos
                if resultado:
                    post_id = resultado.get('id')
                    status = 'actualizado' if post_existente else 'creado'
                    manager.add_imported_post(wp_config_id, enlace, post_id, status)
                    manager.save_content_hash(post_id, contenido_final)
                    print(Fore.GREEN + f"Ítem '{titulo}' {status} con ID: {post_id}")
                    return {"titulo": titulo, "status": status, "post_id": post_id}
                else:
                    raise Exception("No se recibió respuesta válida de WordPress")

            except Exception as e:
                error_msg = f"Error procesando ítem {item_index}: {str(e)}"
                log_in_file_and_db(manager, "ERROR", error_msg)
                print(Fore.RED + error_msg)
                return {"titulo": item.get("title", f"Ítem {item_index}"), "status": "error", "error": str(e)}

        # Si modo asíncrono está activado, se usa ThreadPoolExecutor
        if Config.MODO_ASINCRONO:
            print(Fore.CYAN + f"Procesando en modo asíncrono con {Config.MAX_WORKERS} trabajadores...")
            with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
                future_to_item = {executor.submit(procesar_item, item, i): item for i, item in enumerate(items)}
                for future in as_completed(future_to_item):
                    try:
                        resultado = future.result()
                        resultados.append(resultado)
                    except Exception as e:
                        print(Fore.RED + f"Error en worker: {e}")
        else:
            # Modo secuencial
            print(Fore.CYAN + "Procesando en modo secuencial...")
            for i, item in enumerate(items):
                resultado = procesar_item(item, i)
                resultados.append(resultado)
                # Pequeña pausa para no sobrecargar el servidor
                time.sleep(Config.DELAY_REQUESTS)

        return resultados

    except Exception as e:
        error_msg = f"Error general procesando feed: {str(e)}"
        log_in_file_and_db(manager, "ERROR", error_msg)
        print(Fore.RED + error_msg)
        return []

def configuracion_avanzada():
    """Permite al usuario modificar la configuración avanzada del importador."""
    print(Fore.CYAN + "\n=== CONFIGURACIÓN AVANZADA ===")
    print(Fore.YELLOW + f"1. URL del feed: {Config.FEED_URL}")
    print(Fore.YELLOW + f"2. Número máximo de posts: {Config.MAX_POSTS}")
    print(Fore.YELLOW + f"3. Retraso entre solicitudes: {Config.DELAY_REQUESTS} segundos")
    print(Fore.YELLOW + f"4. Importar imágenes: {'Sí' if Config.IMPORT_IMAGENES else 'No'}")
    print(Fore.YELLOW + f"5. Número máximo de imágenes: {Config.MAX_IMAGENES}")
    print(Fore.YELLOW + f"6. Detectar cambios automáticamente: {'Sí' if Config.AUTO_DETECTAR_CAMBIOS else 'No'}")
    print(Fore.YELLOW + f"7. Modo asíncrono: {'Sí' if Config.MODO_ASINCRONO else 'No'}")
    print(Fore.YELLOW + f"8. Número máximo de trabajadores: {Config.MAX_WORKERS}")
    print(Fore.YELLOW + "9. Volver al menú principal")

    opcion = input(Fore.GREEN + "\nSelecciona una opción para modificar: ")

    if opcion == "1":
        Config.FEED_URL = input(Fore.GREEN + "Nueva URL del feed: ")
    elif opcion == "2":
        try:
            Config.MAX_POSTS = int(input(Fore.GREEN + "Nuevo número máximo de posts: "))
        except ValueError:
            print(Fore.RED + "Valor incorrecto. Debe ser un número entero.")
    elif opcion == "3":
        try:
            Config.DELAY_REQUESTS = float(input(Fore.GREEN + "Nuevo retraso entre solicitudes (segundos): "))
        except ValueError:
            print(Fore.RED + "Valor incorrecto. Debe ser un número.")
    elif opcion == "4":
        respuesta = input(Fore.GREEN + "¿Importar imágenes? (s/n): ").lower()
        Config.IMPORT_IMAGENES = respuesta == "s"
    elif opcion == "5":
        try:
            Config.MAX_IMAGENES = int(input(Fore.GREEN + "Nuevo número máximo de imágenes: "))
        except ValueError:
            print(Fore.RED + "Valor incorrecto. Debe ser un número entero.")
    elif opcion == "6":
        respuesta = input(Fore.GREEN + "¿Detectar cambios automáticamente? (s/n): ").lower()
        Config.AUTO_DETECTAR_CAMBIOS = respuesta == "s"
    elif opcion == "7":
        respuesta = input(Fore.GREEN + "¿Activar modo asíncrono? (s/n): ").lower()
        Config.MODO_ASINCRONO = respuesta == "s"
    elif opcion == "8":
        try:
            Config.MAX_WORKERS = int(input(Fore.GREEN + "Nuevo número máximo de trabajadores: "))
        except ValueError:
            print(Fore.RED + "Valor incorrecto. Debe ser un número entero.")
    elif opcion == "9":
        return
    else:
        print(Fore.RED + "Opción inválida.")

def main():
    """Función principal del importador WordPress."""
    parser = argparse.ArgumentParser(description="Importador WordPress Avanzado")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="config_importador.json")
    parser.add_argument("--tipo", help="Tipo de contenido: posts, paginas o productos", default="posts")
    parser.add_argument("--template", help="Ruta a la plantilla Jinja2 para procesar contenido", default=None)
    parser.add_argument("--modo", help="Modo de ejecución: interactivo o automatico", default="interactivo")
    args = parser.parse_args()

    # Inicializar logging
    log_file = setup_logging()
    logging.info("Iniciando importador WordPress...")

    # Cargar configuración guardada
    Config.load_config(args.config)

    # Mostrar banner
    mostrar_banner()

    # Crear instancia del gestor de configuración
    manager = WPConfigManager()

    # Seleccionar o agregar configuración de WordPress
    wp_config, wp_config_id = seleccionar_configuracion(manager)
    if not wp_config:
        print(Fore.RED + "No se pudo obtener una configuración válida. Finalizando.")
        logging.error("No se pudo obtener una configuración válida.")
        sys.exit(1)

    # Configurar proxy si se definió una lista (en Config, por ejemplo, Config.PROXIES)
    proxy_manager = None
    if hasattr(Config, "PROXIES") and Config.PROXIES:
        proxy_manager = ProxyManager(Config.PROXIES)
        logging.info(f"Configurado sistema de proxies con {len(Config.PROXIES)} direcciones.")

    # Si el modo es automático, ejecutar directamente
    if args.modo.lower() == "automatico":
        logging.info(f"Ejecutando en modo automático. Tipo: {args.tipo}")
        resultados = procesar_feed(Config.FEED_URL, args.tipo, wp_config, wp_config_id, manager, proxy_manager, args.template)
        exportar_estadisticas(manager)
        logging.info(f"Proceso completado. {len(resultados)} ítems procesados.")
        sys.exit(0)

    # Modo interactivo con menú
    opcion = ""
    while opcion != "7":
        opcion = mostrar_menu()

        if opcion == "1":
            # Probar extracción de feed
            print(Fore.GREEN + "Extrayendo feed sin modificar contenido...")
            feed = feedparser.parse(Config.FEED_URL)
            for i, entry in enumerate(feed.entries[:Config.MAX_POSTS]):
                print(f"\n{Fore.CYAN}[{i+1}] {Fore.WHITE}{entry.title}")
                print(f"{Fore.YELLOW}URL: {entry.link}")
                print(f"{Fore.YELLOW}Fecha: {entry.get('published', 'No disponible')}")
                print(f"{Fore.GREEN}Resumen: {BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text()[:150]}...")

        elif opcion == "2":
            # Ejecutar proceso completo
            print(Fore.GREEN + "Ejecutando proceso completo de importación...")
            tipo = input(Fore.YELLOW + "Tipo de contenido (posts, paginas, productos): ").strip().lower() or args.tipo
            template_path = input(Fore.YELLOW + "Ruta a plantilla (opcional, Enter para omitir): ").strip() or args.template

            resultados = procesar_feed(Config.FEED_URL, tipo, wp_config, wp_config_id, manager, proxy_manager, template_path)

            print(f"\n{Fore.CYAN}=== RESUMEN DE IMPORTACIÓN ===")
            estados = {}
            for r in resultados:
                estado = r.get('status', 'desconocido')
                estados[estado] = estados.get(estado, 0) + 1

            for estado, cantidad in estados.items():
                print(f"{Fore.YELLOW}{estado.capitalize()}: {Fore.WHITE}{cantidad}")

            # Exportar estadísticas automáticamente
            if resultados:
                exportar_estadisticas(manager)

        elif opcion == "3":
            # Configuración avanzada
            configuracion_avanzada()

        elif opcion == "4":
            # Ver estadísticas
            print(Fore.GREEN + "Mostrando estadísticas de importación...")
            stats = manager.get_import_statistics()
            print(f"\n{Fore.CYAN}=== ESTADÍSTICAS DE IMPORTACIÓN ===")
            for status, count in stats:
                print(f"{Fore.YELLOW}{status}: {Fore.WHITE}{count}")

        elif opcion == "5":
            # Exportar estadísticas
            print(Fore.GREEN + "Exportando estadísticas...")
            csv_file, json_file = exportar_estadisticas(manager)
            print(Fore.GREEN + f"Estadísticas exportadas a {csv_file} y {json_file}")

        elif opcion == "6":
            # Guardar/cargar configuración
            print(Fore.GREEN + "Guardando configuración actual...")
            Config.save_config(args.config)

        elif opcion == "7":
            # Salir
            print(Fore.YELLOW + "Saliendo del importador...")
            logging.info("Programa finalizado por el usuario.")

        else:
            print(Fore.RED + "Opción inválida, por favor selecciona nuevamente.")

    # Cerrar la conexión a la base de datos
    manager.close()
    print(f"\n{Fore.GREEN}¡Gracias por usar el Importador WordPress Optimizado!")
    print(f"{Fore.CYAN}Log guardado en: {log_file}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.RED + "\nPrograma interrumpido por el usuario.")
        logging.warning("Programa interrumpido por el usuario (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"\nError inesperado: {str(e)}")
        logging.error(f"Error inesperado: {str(e)}")
        sys.exit(1)