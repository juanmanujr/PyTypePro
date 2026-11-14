import re
import logging
import unicodedata

logger = logging.getLogger(__name__)

def _construir_mapa():
    mapa = {}
    # 1. Apóstrofes y comillas simples -> '
    for c in "\u2018\u2019\u201a\u201b\u2032\u02bc\u00b4`":
        mapa[c] = "'"
    # 2. Comillas dobles y angulares -> "
    for c in "\u201c\u201d\u201e\u201f\u2033\u00ab\u00bb":
        mapa[c] = '"'
    # 3. Guiones y rayas -> -
    for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2043\u2212":
        mapa[c] = "-"
    # 4. Puntos suspensivos -> ...
    mapa["\u2026"] = "..."
    # 5. Espacios raros -> espacio normal
    for c in "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\t\n\r\x0b\x0c":
        mapa[c] = " "
    # 6. Caracteres invisibles -> eliminar
    for c in "\u200b\u200c\u200d\u2060\ufeff\u00ad":
        mapa[c] = ""
    # 7. Ligaduras tipográficas -> letras normales
    mapa.update({
        "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
        "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    })
    # 8. Viñetas y puntos medios -> -
    for c in "\u2022\u25cf\u25aa\u25e6\u2023\u00b7\u2219":
        mapa[c] = "-"
    # 9. Símbolos comunes
    mapa["\u2122"] = "TM"
    mapa["\u00a9"] = "(c)"
    mapa["\u00ae"] = "(R)"
    
    # 10. REGLA GENERAL: Símbolos raros (†, ‡, §, etc.) se eliminan
    # En lugar de listarlos, en normalizar_texto() los filtramos directamente.
    
    return {ord(k): v for k, v in mapa.items()}

_MAPA = _construir_mapa()

def normalizar_texto(texto: str) -> str:
    """Convierte caracteres raros de los libros a lo que se puede tipear."""
    if not texto:
        return ""
    
    # Eliminar el bloque "(†)" y similares (daga con paréntesis)
    # Esto se hace antes del translate porque son varios caracteres juntos.
    texto = texto.replace("(†)", "").replace("(‡)", "").replace("(§)", "")
    
    # Normalizar y traducir caracteres conocidos
    texto = unicodedata.normalize("NFC", texto)
    texto = texto.translate(_MAPA)
    
    # --- REGLA GENERAL DE LIMPIEZA ---
    # Elimina cualquier carácter que NO sea letra, número, espacio o puntuación básica.
    # También conserva tildes y diéresis (que son letras modificadas, no símbolos).
    texto = "".join(
        c for c in texto 
        if unicodedata.category(c)[0] in ('L', 'N', 'P', 'Z', 'M') or c in " \t"
    )
    # --------------------------------
    
    # Colapsar espacios múltiples y limpiar extremos
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


class TypingEngine:
    def __init__(self, texto_segmento: str, max_errores_palabra: int = 25):
        # Normalizamos el texto ACÁ, al crear el motor
        texto_limpio = normalizar_texto(texto_segmento)
        
        # Si el texto queda vacío después de limpiar (porque era solo símbolos raros)
        # le ponemos un texto de relleno para que no explote.
        self.texto = texto_limpio if texto_limpio else " "
        
        self.indice_actual = 0
        self.max_errores_palabra = max_errores_palabra

        self.errores_palabra_actual = 0
        self.errores_totales = 0
        self.pulsaciones_totales = 0
        self.caracteres_correctos = 0

        self.estado = "NORMAL"
        self.ultimo_error = None

        self.caracteres_desde_ultimo_guardado = 0
        self.intervalo_guardado = 50

    def procesar_tecla(self, tecla_presionada: str) -> dict:
        if self.indice_actual >= len(self.texto):
            return self._get_estado_actual()

        # --- MANEJO DE BACKSPACE ---
        if tecla_presionada == "Backspace":
            if self.indice_actual > 0:
                self.indice_actual -= 1
                self.estado = "NORMAL"
                self.errores_palabra_actual = 0
                self.ultimo_error = None
                if self.caracteres_desde_ultimo_guardado > 0:
                    self.caracteres_desde_ultimo_guardado -= 1
            return self._get_estado_actual()

        # Normalizamos la tecla presionada también (por si tipeás algo raro con Alt)
        tecla_normalizada = normalizar_texto(tecla_presionada) if tecla_presionada != " " else " "
        if not tecla_normalizada:
            # Si la tecla normalizada queda vacía (era un símbolo raro), la ignoramos
            return self._get_estado_actual()

        tecla_presionada = tecla_normalizada
        caracter_esperado = self.texto[self.indice_actual]

        if self.estado == "DESFASE":
            return self._get_estado_actual()

        self.pulsaciones_totales += 1

        if tecla_presionada == caracter_esperado:
            self.estado = "NORMAL"
            self.ultimo_error = None
            self.caracteres_correctos += 1
            self.indice_actual += 1
            self.caracteres_desde_ultimo_guardado += 1
            if caracter_esperado == " ":
                self.errores_palabra_actual = 0
        else:
            self.estado = "ERROR"
            self.ultimo_error = tecla_presionada
            self.errores_palabra_actual += 1
            self.errores_totales += 1
            if self.errores_palabra_actual >= self.max_errores_palabra:
                self.estado = "DESFASE"

        return self._get_estado_actual()

    def necesita_guardar(self) -> bool:
        return self.caracteres_desde_ultimo_guardado >= self.intervalo_guardado

    def resetear_contador_guardado(self):
        self.caracteres_desde_ultimo_guardado = 0

    def _get_estado_actual(self) -> dict:
        return {
            "estado": self.estado,
            "indice_actual": self.indice_actual,
            "indice_maximo": len(self.texto),
            "errores_palabra_actual": self.errores_palabra_actual,
            "errores_totales": self.errores_totales,
            "ultimo_error": self.ultimo_error,
            "completado": self.indice_actual >= len(self.texto)
        }