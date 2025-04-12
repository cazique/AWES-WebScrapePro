"""
Módulo de gestión de base de datos para el importador WordPress.

Proporciona clases y funciones para manejar la configuración y el registro de
importaciones a través de una base de datos SQLite.
"""

import sqlite3
import hashlib
import time
from datetime import datetime
import os
import logging
from colorama import Fore

# Ruta por defecto para la base de datos SQLite
DB_FILE = 'wp_importer.db'


def log_in_file_and_db(manager, level, message):
    """
    Registra un mensaje tanto en el archivo de log como en la base de datos.

    Args:
        manager: Instancia de WPConfigManager (puede ser None)
        level: Nivel de log ('INFO', 'ERROR', 'WARNING')
        message: Mensaje a registrar
    """
    if level.upper() == 'INFO':
        logging.info(message)
    elif level.upper() == 'ERROR':
        logging.error(message)
    else:
        logging.warning(message)

    # Si se proporcionó un manager, también registramos en la BD
    if manager:
        manager.log_to_db(level, message)


class WPConfigManager:
    """
    Gestiona la configuración y el registro de importaciones en una base de datos SQLite.

    Esta clase proporciona métodos para:
    - Guardar y recuperar configuraciones de WordPress
    - Registrar posts importados y su estado
    - Almacenar hashes de contenido para detectar cambios
    - Mantener logs de operaciones
    """

    def __init__(self, db_file=DB_FILE):
        """
        Inicializa el gestor de configuración y crea las tablas necesarias.

        Args:
            db_file: Ruta del archivo de base de datos SQLite (opcional)
        """
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        # Habilitar claves foráneas para mantener integridad referencial
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Crear las tablas si no existen
        self.create_config_table()
        self.create_imported_table()
        self.create_content_hash_table()
        self.create_logs_table()

        logging.info(f"Base de datos inicializada: {self.db_file}")

    def create_config_table(self):
        """Crea la tabla de configuraciones de WordPress si no existe."""
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS wordpress_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wp_url TEXT NOT NULL,
                wp_user TEXT NOT NULL,
                wp_pass TEXT NOT NULL,
                site_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

    def create_imported_table(self):
        """Crea la tabla de posts importados si no existe."""
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS imported_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wp_config_id INTEGER NOT NULL,
                original_url TEXT NOT NULL,
                post_id INTEGER,
                status TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(wp_config_id, original_url),
                FOREIGN KEY(wp_config_id) REFERENCES wordpress_config(id) ON DELETE CASCADE
            );
            """)

    def create_content_hash_table(self):
        """Crea la tabla de hashes de contenido si no existe."""
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS content_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                hash_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, content_hash)
            );
            """)

    def create_logs_table(self):
        """Crea la tabla de logs si no existe."""
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS import_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

    def log_to_db(self, level, message):
        """
        Registra un mensaje en la tabla de logs.

        Args:
            level: Nivel del log ('INFO', 'ERROR', 'WARNING')
            message: Mensaje a registrar
        """
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO import_logs (level, message, created_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (level, message))
        except sqlite3.Error as e:
            logging.error(f"Error al registrar en la BD: {e}")

    def list_configurations(self):
        """
        Obtiene la lista de configuraciones de WordPress.

        Returns:
            list: Lista de tuplas con las configuraciones
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, wp_url, wp_user, site_name, datetime(last_used) as last_used
            FROM wordpress_config
            ORDER BY last_used DESC
        """)
        return cur.fetchall()

    def add_configuration(self, wp_url, wp_user, wp_pass, site_name=None):
        """
        Añade una nueva configuración de WordPress.

        Args:
            wp_url: URL base de la API REST de WordPress
            wp_user: Nombre de usuario
            wp_pass: Contraseña o token de aplicación
            site_name: Nombre descriptivo del sitio (opcional)

        Returns:
            int: ID de la configuración añadida
        """
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO wordpress_config (wp_url, wp_user, wp_pass, site_name) VALUES (?, ?, ?, ?)",
                (wp_url, wp_user, wp_pass, site_name)
            )
            config_id = cursor.lastrowid
            log_in_file_and_db(self, "INFO", f"Nueva configuración añadida con ID {config_id}.")
            return config_id

    def get_configuration_by_id(self, config_id):
        """
        Obtiene una configuración por su ID y actualiza la fecha de último uso.

        Args:
            config_id: ID de la configuración a obtener

        Returns:
            tuple: Datos de la configuración o None si no existe
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, wp_url, wp_user, wp_pass, site_name 
            FROM wordpress_config 
            WHERE id = ?
        """, (config_id,))
        config = cur.fetchone()
        if config:
            with self.conn:
                self.conn.execute("""
                    UPDATE wordpress_config 
                    SET last_used = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (config_id,))
        return config

    def delete_configuration(self, config_id):
        """
        Elimina una configuración por su ID.

        Args:
            config_id: ID de la configuración a eliminar

        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            with self.conn:
                cursor = self.conn.execute("DELETE FROM wordpress_config WHERE id = ?", (config_id,))
                deleted = cursor.rowcount > 0
                if deleted:
                    log_in_file_and_db(self, "INFO", f"Configuración {config_id} eliminada.")
                return deleted
        except sqlite3.Error as e:
            log_in_file_and_db(self, "ERROR", f"Error al eliminar configuración {config_id}: {e}")
            return False

    def check_imported_post(self, wp_config_id, original_url):
        """
        Verifica si un post ya ha sido importado.

        Args:
            wp_config_id: ID de la configuración de WordPress
            original_url: URL original del post

        Returns:
            tuple: Datos del post importado o None si no existe
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, wp_config_id, original_url, post_id, status, datetime(last_updated) as last_updated
            FROM imported_posts
            WHERE wp_config_id = ? AND original_url = ?
        """, (wp_config_id, original_url))
        return cur.fetchone()

    def add_imported_post(self, wp_config_id, original_url, post_id, status):
        """
        Registra un post importado o actualiza su estado.

        Args:
            wp_config_id: ID de la configuración de WordPress
            original_url: URL original del post
            post_id: ID del post en WordPress
            status: Estado del post ('creado', 'actualizado', 'error', etc.)
        """
        try:
            with self.conn:
                self.conn.execute("""
                INSERT OR REPLACE INTO imported_posts 
                (wp_config_id, original_url, post_id, status, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (wp_config_id, original_url, post_id, status))
                log_in_file_and_db(self, "INFO",
                                   f"Registro importación actualizado para '{original_url}' con status '{status}'.")
        except sqlite3.Error as e:
            log_in_file_and_db(self, "ERROR", f"Error al registrar post importado: {e}")

    def save_content_hash(self, post_id, content):
        """
        Guarda el hash del contenido de un post para detectar cambios.

        Args:
            post_id: ID del post en WordPress
            content: Contenido del post

        Returns:
            str: Hash MD5 del contenido
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()
        try:
            with self.conn:
                self.conn.execute("""
                INSERT OR REPLACE INTO content_hashes 
                (post_id, content_hash, hash_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (post_id, content_hash))
            return content_hash
        except sqlite3.Error as e:
            log_in_file_and_db(self, "ERROR", f"Error al guardar hash de contenido: {e}")
            return content_hash

    def content_changed(self, post_id, new_content):
        """
        Verifica si el contenido de un post ha cambiado.

        Args:
            post_id: ID del post en WordPress
            new_content: Nuevo contenido a comparar

        Returns:
            bool: True si el contenido cambió, False en caso contrario
        """
        new_hash = hashlib.md5(new_content.encode()).hexdigest()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT content_hash FROM content_hashes
            WHERE post_id = ?
            ORDER BY hash_date DESC
            LIMIT 1
        """, (post_id,))
        result = cur.fetchone()
        if not result:
            return True
        return new_hash != result[0]

    def get_import_statistics(self, wp_config_id=None):
        """
        Obtiene estadísticas de importación.

        Args:
            wp_config_id: ID de la configuración (opcional, si None se obtienen todas)

        Returns:
            list: Lista de tuplas (status, count) con las estadísticas
        """
        cur = self.conn.cursor()
        if wp_config_id:
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM imported_posts 
                WHERE wp_config_id = ?
                GROUP BY status
            """, (wp_config_id,))
        else:
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM imported_posts 
                GROUP BY status
            """)
        return cur.fetchall()

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            logging.info("Conexión a base de datos cerrada.")