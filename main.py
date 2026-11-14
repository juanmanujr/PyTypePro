import sys
import time
import os
import html
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, QInputDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from core.engine import TypingEngine
from core.pdf_processor import PDFProcessor
from core.database import DatabaseManager

class LectorPDFThread(QThread):
    pagina_lista = pyqtSignal(int, int, int, list, str)
    terminado = pyqtSignal(int, list)
    error = pyqtSignal(str)

    def __init__(self, db, book_id, ruta_archivo, procesador, pagina_inicio=1, pendiente=""):
        super().__init__()
        self.db = db
        self.book_id = book_id
        self.ruta_archivo = ruta_archivo
        self.procesador = procesador
        self.pagina_inicio = pagina_inicio
        self.pendiente = pendiente
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            def al_pagina(pag, tot, segs, pend):
                guardado = self.db.guardar_pagina(self.book_id, pag + 1, segs, pend)
                self.pagina_lista.emit(self.book_id, pag, tot, segs if guardado else [], pend)

            resto = self.procesador.extract_and_clean_stream(
                self.ruta_archivo,
                callback_pagina=al_pagina,
                pagina_inicio=self.pagina_inicio,
                texto_pendiente=self.pendiente,
                cancelar=lambda: self._cancelar,
            )
            if not self._cancelar:
                self.db.finalizar_libro(self.book_id, resto)
                self.terminado.emit(self.book_id, resto)
        except Exception as e:
            self.error.emit(str(e))

class PyTypeProWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyType Pro - Lector de Libros")
        self.setMinimumSize(900, 500)
        
        self.db = DatabaseManager()
        self.procesador_pdf = PDFProcessor()
        self.segmentos = []
        self.indice_segmento_actual = 0
        self.motor = None
        self.book_id = None
        self.tiempo_inicio = 0
        self.hilo_pdf = None
        self.ruta_actual = ""
        
        self.setup_ui()
        self.cargar_ultimo_libro()

        # Aseguramos que la ventana principal tenga el foco del teclado
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        top_layout = QHBoxLayout()
        self.btn_abrir = QPushButton("Biblioteca / Agregar PDF")
        self.btn_abrir.setFont(QFont("Arial", 12))
        self.btn_abrir.setFocusPolicy(Qt.FocusPolicy.NoFocus) # <-- LA SOLUCION MAGICA
        self.btn_abrir.clicked.connect(self.abrir_biblioteca)
        top_layout.addWidget(self.btn_abrir)
        top_layout.addStretch()
        
        self.label_progreso_pdf = QLabel("")
        self.label_progreso_pdf.setStyleSheet("color: #888; font-size: 10px;")
        top_layout.addWidget(self.label_progreso_pdf)
        
        layout.addLayout(top_layout)

        self.label_texto = QLabel()
        self.label_texto.setFont(QFont("Courier New", 20))
        self.label_texto.setWordWrap(True)
        self.label_texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_texto, 1)

    def cargar_ultimo_libro(self):
        book_id = self.db.obtener_ultimo_progreso()
        if book_id:
            self.cargar_libro_desde_db(book_id)
        else:
            self.label_texto.setText("<h2 style='color: #888;'>Haz clic en 'Biblioteca / Agregar PDF' para comenzar.</h2>")

    def abrir_biblioteca(self):
        libros = self.db.obtener_todos_los_libros()
        if not libros:
            self.seleccionar_nuevo_pdf()
            return

        opciones = ["[+] Agregar nuevo PDF"]
        for lib in libros:
            opciones.append(f"{lib[1]}")

        opcion, ok = QInputDialog.getItem(self, "Biblioteca", "Selecciona un libro:", opciones, 0, False)
        
        if ok and opcion:
            if opcion == "[+] Agregar nuevo PDF":
                self.seleccionar_nuevo_pdf()
            else:
                for lib in libros:
                    if lib[1] == opcion:
                        self.cargar_libro_desde_db(lib[0])
                        break
        # Al cerrar la ventana modal, devolvemos el foco
        self.setFocus()

    def seleccionar_nuevo_pdf(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar Libro PDF", "", "Archivos PDF (*.pdf)")
        if archivo:
            self.ruta_actual = archivo
            self.procesar_nuevo_pdf(archivo)

    def procesar_nuevo_pdf(self, ruta_archivo):
        titulo = os.path.basename(ruta_archivo).replace(".pdf", "")
        book_id = self.db.guardar_libro(titulo, ruta_archivo)
        self.cargar_libro_desde_db(book_id)

    def detener_hilo(self):
        if self.hilo_pdf and self.hilo_pdf.isRunning():
            self.hilo_pdf.cancelar()
            self.hilo_pdf.wait()
            QApplication.processEvents()
        self.hilo_pdf = None

    def iniciar_hilo_lectura(self, book_id, ruta, pagina_inicio, pendiente):
        self.hilo_pdf = LectorPDFThread(self.db, book_id, ruta, self.procesador_pdf, pagina_inicio, pendiente)
        self.hilo_pdf.pagina_lista.connect(self.al_leer_pagina)
        self.hilo_pdf.terminado.connect(self.al_terminar_libro)
        self.hilo_pdf.error.connect(lambda err: self.label_texto.setText(f"<h2 style='color: red;'>Error:</h2>{err}"))
        self.hilo_pdf.start(QThread.Priority.LowPriority)

    def al_leer_pagina(self, book_id, pagina, total, segmentos, pendiente):
        if book_id != self.book_id:
            return
        self.label_progreso_pdf.setText(f"Cargando pagina {pagina} de {total}...")
        self.segmentos.extend(segmentos)
        
        if self.motor is None:
            self.cargar_segmento_actual()

    def al_terminar_libro(self, book_id, segmentos_finales):
        if book_id != self.book_id:
            return
        self.segmentos.extend(segmentos_finales)
        self.label_progreso_pdf.setText("")
        if self.motor is None:
            self.cargar_segmento_actual()
        print("[INFO] Libro completo guardado.")

    def cargar_libro_desde_db(self, book_id):
        self.detener_hilo()
        self.btn_abrir.setEnabled(True)
        self.label_progreso_pdf.setText("")

        libro = self.db.obtener_libro_por_id(book_id)
        if not libro:
            return

        self.book_id, _, self.ruta_actual, completo, pagina_actual, pendiente = libro
        self.motor = None
        self.segmentos = self.db.obtener_segmentos(self.book_id)
        self.indice_segmento_actual = min(self.db.obtener_sesion(self.book_id), len(self.segmentos))
        self.db.actualizar_progreso_libro(self.book_id)

        if not completo:
            self.iniciar_hilo_lectura(self.book_id, self.ruta_actual, pagina_actual, pendiente)

        self.cargar_segmento_actual()

    def cargar_segmento_actual(self):
        if self.indice_segmento_actual < len(self.segmentos):
            self.motor = TypingEngine(self.segmentos[self.indice_segmento_actual])
            self.tiempo_inicio = time.time()
            self.actualizar_vista()
        else:
            self.motor = None
            if self.hilo_pdf and self.hilo_pdf.isRunning():
                self.label_texto.setText("<h2>Cargando mas texto...</h2>")
            else:
                self.label_texto.setText("<h2>Fin del libro</h2>")

    def actualizar_vista(self):
        if not self.motor:
            return
        html_parts = []
        estado = self.motor._get_estado_actual()
        indice = estado["indice_actual"]
        texto_actual = self.segmentos[self.indice_segmento_actual]
        
        for i, letra in enumerate(texto_actual):
            safe_letra = html.escape(letra)
            if i < indice:
                if estado["estado"] == "ERROR" and i == indice - 1:
                    html_parts.append(f"<span style='color: #ff4c4c;'>{safe_letra}</span>")
                else:
                    html_parts.append(f"<span style='color: #4caf50;'>{safe_letra}</span>")
            elif i == indice:
                html_parts.append(f"<span style='background-color: #444; color: #ffffff; border-bottom: 2px solid #fff;'>{safe_letra}</span>")
            else:
                html_parts.append(f"<span style='color: #666666;'>{safe_letra}</span>")
        self.label_texto.setText("".join(html_parts))

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        if not self.motor:
            return
        tecla = event.text()
        if event.key() == Qt.Key.Key_Backspace:
            tecla = "Backspace"
        if not tecla:
            return

        self.motor.procesar_tecla(tecla)
        self.actualizar_vista()
        
        if self.motor.necesita_guardar() and self.book_id:
            self.db.guardar_sesion(self.book_id, self.indice_segmento_actual)
            self.motor.resetear_contador_guardado()

        if self.motor._get_estado_actual()["completado"] and self.motor.indice_actual > 0:
            self.finalizar_segmento()

    def finalizar_segmento(self):
        self.indice_segmento_actual += 1
        if self.book_id:
            self.db.guardar_sesion(self.book_id, self.indice_segmento_actual)
            
        if self.indice_segmento_actual < len(self.segmentos):
            self.cargar_segmento_actual()
        else:
            self.cargar_segmento_actual()

    def closeEvent(self, event):
        if self.book_id:
            self.db.guardar_sesion(self.book_id, self.indice_segmento_actual)
        self.detener_hilo()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = PyTypeProWindow()
    ventana.show()
    sys.exit(app.exec())