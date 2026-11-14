# PyType Pro

Aplicación de escritorio para Windows que permite practicar mecanografía mientras leés un libro en PDF.

## Características (MVP)

- **Carga en segundo plano:** procesa libros de cientos de páginas sin congelar la interfaz, así que podés empezar a escribir desde la primera página.
- **Motor de tipeo:** detecta errores en tiempo real y se bloquea tras errores repetidos en una misma palabra.
- **Memoria de lectura:** guarda en SQLite el avance de la carga y el segmento donde quedaste, y retoma desde ahí al reabrir.
- **Biblioteca:** permite agregar varios PDF y volver a cualquiera de ellos.
- **Interfaz minimalista** hecha con PyQt6.

## Tecnologías

Python 3.10, PyQt6, SQLite3, pdfplumber y PyInstaller.

## Cómo ejecutarlo

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/juanmanujr/PyTypePro.git
   cd PyTypePro
   ```
2. Crear y activar un entorno virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Instalar las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecutar la aplicación:
   ```bash
   python main.py
   ```

## Cómo se usa

1. Hacé clic en **Biblioteca / Agregar PDF** y elegí un libro.
2. Escribí el texto que aparece en pantalla. Verde significa correcto, rojo significa error.
3. Al cerrar la app, tu progreso queda guardado y se retoma al abrirla de nuevo.
4. Con **Esc** cerrás la aplicación.

## Próximamente

- [ ] WPM y precisión en tiempo real
- [ ] Historial de sesiones y gráficos de progreso
- [ ] Retomar en la letra exacta dentro del segmento

## Autor

**JuanMa**, estudiante de Ingeniería Informática 
GitHub: [@juanmanujr](https://github.com/juanmanujr)