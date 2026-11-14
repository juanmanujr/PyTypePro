import logging

logger = logging.getLogger(__name__)

class TypingEngine:
    def __init__(self, texto_segmento: str, max_errores_palabra: int = 25):
        self.texto = texto_segmento
        self.indice_actual = 0
        self.max_errores_palabra = max_errores_palabra
        
        self.errores_palabra_actual = 0
        self.errores_totales = 0
        self.pulsaciones_totales = 0
        self.caracteres_correctos = 0
        
        self.estado = "NORMAL"
        self.ultimo_error = None
        
        # Para el guardado automatico cada 50 caracteres
        self.caracteres_desde_ultimo_guardado = 0
        self.intervalo_guardado = 50

    def procesar_tecla(self, tecla_presionada: str) -> dict:
        if self.indice_actual >= len(self.texto):
            return self._get_estado_actual()

        caracter_esperado = self.texto[self.indice_actual]

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

        # --- SI ESTAMOS EN EL MURO (DESFASE) ---
        if self.estado == "DESFASE":
            return self._get_estado_actual()

        # --- TECLA NORMAL ---
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