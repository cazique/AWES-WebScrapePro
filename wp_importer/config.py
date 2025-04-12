"""
Módulo de configuración para el importador WordPress.

Contiene la clase Config que almacena y gestiona la configuración global del importador.
"""

import json
import os
import logging
from colorama import Fore


class Config:
    """
    Clase para almacenar y manejar la configuración global del importador.
    Se puede cargar y guardar en un archivo JSON.
    """
    # Configuración WordPress
    WP_URL = ""
    WP_USER = ""
    WP_PASS = ""

    # Configuración de importación
    FEED_URL = "https://torquemag.io/category/development/feed/"
    MAX_POSTS = 5
    DELAY_REQUESTS = 3
    MAX_IMAGENES = 5
    IMPORT_IMAGENES = True
    IMPORT_VIDEOS = False
    IMPORT_TEXTO = True
    AUTO_DETECTAR_CAMBIOS = True

    # Configuración avanzada
    MODO_ASINCRONO = False
    MAX_WORKERS = 3

    # Listas opcionales
    CATEGORIES = []
    TAGS = []
    AUTHOR_ID = None

    # Configuración de proxies (si se utiliza)
    PROXIES = [
        # Ejemplos de proxies (comentados para evitar su uso accidental)
        # "http://user:pass@proxy1.example.com:8080",
        # "http://proxy2.example.com:8080"
    ]

    @staticmethod
    def save_config(filename="config_importador.json"):
        """
        Guarda la configuración actual en un archivo JSON.

        Args:
            filename (str): Ruta del archivo donde guardar la configuración

        Returns:
            bool: True si se guardó correctamente, False en caso contrario
        """
        # Filtra solo los atributos en mayúscula (por convención, los atributos de configuración)
        config_data = {key: value for key, value in Config.__dict__.items() if key.isupper()}
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            print(Fore.GREEN + f"Configuración guardada en {filename}")
            logging.info(f"Configuración guardada en {filename}")
            return True
        except Exception as e:
            print(Fore.RED + f"Error al guardar configuración: {e}")
            logging.error(f"Error al guardar configuración: {e}")
            return False

    @staticmethod
    def load_config(filename="config_importador.json"):
        """
        Carga la configuración desde un archivo JSON.

        Args:
            filename (str): Ruta del archivo de configuración a cargar

        Returns:
            bool: True si se cargó correctamente, False en caso contrario
        """
        try:
            # Intentar cargar desde variables de entorno primero
            if os.getenv("WP_API_URL"):
                Config.WP_URL = os.getenv("WP_API_URL")
            if os.getenv("WP_USER"):
                Config.WP_USER = os.getenv("WP_USER")
            if os.getenv("WP_PASS"):
                Config.WP_PASS = os.getenv("WP_PASS")
            if os.getenv("WP_FEED_URL"):
                Config.FEED_URL = os.getenv("WP_FEED_URL")

            # Luego intentar cargar desde archivo
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(Config, key):
                        setattr(Config, key, value)
                print(Fore.GREEN + f"Configuración cargada desde {filename}")
                logging.info(f"Configuración cargada desde {filename}")
                return True
            return False
        except Exception as e:
            print(Fore.RED + f"Error al cargar configuración: {e}")
            logging.error(f"Error al cargar configuración: {e}")
            return False