# GastoTrack

Aplicación personal para registrar tickets de compra mediante Telegram, extraer datos con OCR (Tesseract), permitir corrección rápida y consultar estadísticas con Streamlit.

## Características

- 📸 Envío de fotos de tickets por Telegram
- 🔍 Extracción automática de datos con OCR (Tesseract)
- ✏️ Corrección rápida de datos (10-15 segundos)
- 💾 Almacenamiento en base de datos SQLite local
- 📊 Dashboard de estadísticas con Streamlit
- 🏷️ Clasificación automática de productos por categoría

## Requisitos del sistema

- Python 3.12
- Poetry (gestor de dependencias)
- Tesseract OCR

### Instalación de Tesseract

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-spa
```

#### macOS

```bash
brew install tesseract tesseract-lang
```

#### Verificar instalación

```bash
tesseract --version
```

## Instalación

1. Clonar el repositorio:

```bash
git clone <url-del-repositorio>
cd project-gastotrack
```

2. Configurar Poetry para usar entorno virtual in-project:

```bash
poetry config virtualenvs.in-project true
```

3. Instalar dependencias:

```bash
poetry install
```

4. Configurar variables de entorno:

```bash
cp .env.example .env
```

Editar `.env` y añadir tu token de Telegram Bot (obtenerlo en [@BotFather](https://t.me/BotFather)).

## Uso

### Ejecutar el bot de Telegram

```bash
poetry run python -m gastotrack.bot
```

### Ejecutar el dashboard

```bash
poetry run streamlit run src/gastotrack/dashboard.py
```

## Flujo de trabajo

1. Enviar foto de ticket al bot de Telegram
2. El bot procesa la imagen con OCR y devuelve un resumen
3. Revisar y corregir datos si es necesario con comandos:
   - `confirmar` - Guardar ticket
   - `precio <n> <nuevo_precio>` - Corregir precio de línea
   - `categoria <n> <nueva_categoria>` - Corregir categoría
   - `eliminar <n>` - Eliminar línea
   - `fecha <YYYY-MM-DD>` - Cambiar fecha
   - `cancelar` - Descartar ticket
4. Consultar estadísticas en el dashboard

## Estructura del proyecto

```
project-gastotrack/
├── src/gastotrack/       # Código fuente
│   ├── bot.py            # Bot de Telegram
│   ├── ocr.py            # Procesamiento OCR
│   ├── parser.py         # Parseo de tickets
│   ├── clasificador.py   # Clasificación de productos
│   ├── bd.py             # Capa de base de datos
│   ├── modelos.py        # Modelos de datos
│   ├── config.py         # Configuración
│   └── dashboard.py      # Dashboard Streamlit
├── datos/                # Datos persistentes
│   ├── categorias.json   # Diccionario de categorías
│   └── gastotrack.db     # Base de datos SQLite
├── tickets_images/       # Imágenes de tickets
└── tests/                # Tests
```

## Prueba Manual con Imagen

Para probar el OCR, parser y clasificador con una imagen de ticket real:

1. Coloca una foto de un ticket en el directorio `test_data/`:

```bash
# Por ejemplo, copia una foto desde tu móvil
cp ~/Descargas/ticket.jpg test_data/
```

2. Ejecuta el script de prueba manual:

```bash
poetry run python test_manual.py test_data/ticket.jpg
```

El script mostrará:
- ✅ Texto extraído por OCR
- ✅ Productos detectados con precios
- ✅ Clasificación automática por categoría
- ✅ Resumen completo del ticket

Ver [`test_data/README.md`](test_data/README.md) para más detalles.

## Tests

Ejecutar tests unitarios:

```bash
poetry run pytest
```

## Licencia

Uso personal.
