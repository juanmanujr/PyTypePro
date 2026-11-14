import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="pytype_pro.db"):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        # timeout=10 evita bloqueos si el hilo y la ventana escriben casi al mismo tiempo
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")     # Permite leer mientras se escribe
        conn.execute("PRAGMA synchronous = NORMAL")    # Escrituras mas rapidas
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self):
        try:
            with self._get_connection() as conn:
                # 1. Libros
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        titulo TEXT NOT NULL,
                        autor TEXT,
                        ruta_archivo TEXT UNIQUE,
                        completo INTEGER DEFAULT 0,
                        pagina_actual INTEGER DEFAULT 1,
                        texto_pendiente TEXT DEFAULT '',
                        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Parche por si el usuario tiene una DB vieja (agrega columnas si faltan)
                columnas = [c[1] for c in conn.execute("PRAGMA table_info(books)").fetchall()]
                if "texto_pendiente" not in columnas:
                    conn.execute("ALTER TABLE books ADD COLUMN texto_pendiente TEXT DEFAULT ''")

                # 2. Segmentos (El texto troceado)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS segments (
                        book_id INTEGER NOT NULL,
                        idx INTEGER NOT NULL,
                        texto TEXT NOT NULL,
                        PRIMARY KEY (book_id, idx),
                        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
                    )
                ''')

                # 3. Sesiones (Por donde va el usuario)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        indice_actual INTEGER DEFAULT 0,
                        session_status TEXT DEFAULT 'En curso',
                        fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
                    )
                ''')

                # 4. Progreso (Ultimo libro abierto)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER UNIQUE,
                        ultima_vez DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
                    )
                ''')
        except sqlite3.Error as e:
            logger.error(f"Error DB: {e}")
            raise

    def guardar_libro(self, titulo, ruta):
        """Crea el libro si no existe y devuelve su ID."""
        with self._get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO books (titulo, ruta_archivo) VALUES (?, ?)", (titulo, ruta))
            return conn.execute("SELECT id FROM books WHERE ruta_archivo = ?", (ruta,)).fetchone()[0]

    def guardar_pagina(self, book_id, pagina_siguiente, segmentos, pendiente):
        """Guarda los segmentos de una pagina en una sola transaccion."""
        with self._get_connection() as conn:
            # Verificamos que no estemos guardando una pagina vieja (por si el hilo se duplica)
            fila = conn.execute("SELECT pagina_actual FROM books WHERE id = ?", (book_id,)).fetchone()
            if not fila or pagina_siguiente <= fila[0]:
                return False
                
            inicio = conn.execute("SELECT COALESCE(MAX(idx) + 1, 0) FROM segments WHERE book_id = ?", (book_id,)).fetchone()[0]
            
            # Insertamos todos los segmentos de golpe
            conn.executemany(
                "INSERT INTO segments (book_id, idx, texto) VALUES (?, ?, ?)",
                [(book_id, inicio + n, s) for n, s in enumerate(segmentos)]
            )
            
            # Actualizamos la pagina actual y el texto que quedo pendiente
            conn.execute(
                "UPDATE books SET pagina_actual = ?, texto_pendiente = ? WHERE id = ?",
                (pagina_siguiente, pendiente, book_id)
            )
            return True

    def finalizar_libro(self, book_id, segmentos_finales):
        """Guarda el ultimo resto de texto y marca el libro como completo."""
        with self._get_connection() as conn:
            if segmentos_finales:
                inicio = conn.execute("SELECT COALESCE(MAX(idx) + 1, 0) FROM segments WHERE book_id = ?", (book_id,)).fetchone()[0]
                conn.executemany(
                    "INSERT INTO segments (book_id, idx, texto) VALUES (?, ?, ?)",
                    [(book_id, inicio + n, s) for n, s in enumerate(segmentos_finales)]
                )
            conn.execute("UPDATE books SET completo = 1, texto_pendiente = '' WHERE id = ?", (book_id,))

    def obtener_segmentos(self, book_id):
        """Devuelve todos los segmentos de un libro ordenados."""
        with self._get_connection() as conn:
            filas = conn.execute("SELECT texto FROM segments WHERE book_id = ? ORDER BY idx", (book_id,)).fetchall()
            return [f[0] for f in filas]

    def obtener_todos_los_libros(self):
        with self._get_connection() as conn:
            return conn.execute("SELECT id, titulo, completo FROM books ORDER BY fecha_creacion DESC").fetchall()

    def obtener_ultimo_progreso(self):
        with self._get_connection() as conn:
            row = conn.execute("SELECT book_id FROM progress ORDER BY ultima_vez DESC LIMIT 1").fetchone()
            return row[0] if row else None

    def actualizar_progreso_libro(self, book_id):
        with self._get_connection() as conn:
            conn.execute("INSERT INTO progress (book_id, ultima_vez) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(book_id) DO UPDATE SET ultima_vez=CURRENT_TIMESTAMP", (book_id,))

    def guardar_sesion(self, book_id, indice_actual):
        """Guarda el segmento en el que estas escribiendo."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT id FROM sessions WHERE book_id = ? AND session_status = 'En curso'", (book_id,)).fetchone()
                if row:
                    conn.execute("UPDATE sessions SET indice_actual = ? WHERE id = ?", (indice_actual, row[0]))
                else:
                    conn.execute("INSERT INTO sessions (book_id, indice_actual) VALUES (?, ?)", (book_id, indice_actual))
        except sqlite3.Error as e:
            logger.error(f"Error al guardar sesion: {e}")

    def obtener_sesion(self, book_id):
        with self._get_connection() as conn:
            row = conn.execute("SELECT indice_actual FROM sessions WHERE book_id = ? AND session_status = 'En curso' ORDER BY id DESC LIMIT 1", (book_id,)).fetchone()
            return row[0] if row else 0

    def obtener_libro_por_id(self, book_id):
        """Devuelve (id, titulo, ruta, completo, pagina_actual, texto_pendiente)."""
        with self._get_connection() as conn:
            return conn.execute("SELECT id, titulo, ruta_archivo, completo, pagina_actual, COALESCE(texto_pendiente, '') FROM books WHERE id = ?", (book_id,)).fetchone()