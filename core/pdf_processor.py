import re
import logging
import pdfplumber
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFProcessor:
    def extract_and_clean_stream(self, pdf_path, callback_pagina, pagina_inicio=1, texto_pendiente="", cancelar=None):
        ruta = Path(pdf_path)
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontro el archivo: {pdf_path}")

        try:
            with pdfplumber.open(ruta) as pdf:
                total = len(pdf.pages)
                for i in range(pagina_inicio, total + 1):
                    if cancelar and cancelar():
                        return []
                    
                    # Extraemos el texto de la pagina actual
                    texto_pagina = pdf.pages[i - 1].extract_text() or ""
                    texto_limpio = self._limpiar_texto(texto_pagina)
                    
                    # Lo unimos con lo que habia quedado pendiente de la pagina anterior
                    texto_combinado = f"{texto_pendiente} {texto_limpio}".strip()
                    
                    # Lo dividimos en segmentos
                    segmentos, texto_pendiente = self.segmentar_por_oraciones(texto_combinado, max_caracteres=300)
                    
                    # Avisamos a la interfaz (o al hilo) que esta pagina ya esta lista
                    if callback_pagina:
                        callback_pagina(i, total, segmentos, texto_pendiente)
                        
                    # Pequeña pausa para no saturar a la ventana grafica
                    time.sleep(0.02)
                    
        except Exception as e:
            logger.error(f"Error al leer el PDF: {e}")
            raise

        # Al terminar todas las paginas, devolvemos el ultimo pedazo de texto que sobro
        resto = texto_pendiente.strip()
        return [resto] if resto else []

    def _limpiar_texto(self, texto: str) -> str:
        if not texto:
            return ""
        # Reemplazamos saltos de linea por espacios y quitamos espacios dobles
        texto = texto.replace('\n', ' ').replace('\r', ' ')
        texto = re.sub(r'\s+', ' ', texto)
        # Unimos palabras que quedaron cortadas por guiones al final de linea
        texto = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', texto)
        # Quitamos espacios antes de signos de puntuacion
        texto = re.sub(r'\s+([.,;:!?])', r'\1', texto)
        return texto.strip()

    def segmentar_por_oraciones(self, texto: str, max_caracteres: int = 300):
        """Devuelve (lista_de_segmentos, texto_pendiente)."""
        # Separamos por punto, exclamacion o interrogacion
        oraciones = re.split(r'(?<=[.!?])\s+', texto.strip())
        segmentos = []
        actual = ""
        
        for oracion in oraciones:
            oracion = oracion.strip()
            if not oracion:
                continue
                
            if not actual:
                actual = oracion
            elif len(actual) + 1 + len(oracion) <= max_caracteres:
                actual += " " + oracion
            else:
                segmentos.append(actual)
                actual = oracion
                
        # Devolvemos los segmentos completos y el texto que quedo a medias
        return segmentos, actual