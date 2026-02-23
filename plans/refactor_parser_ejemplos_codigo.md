# Ejemplos de Código para Refactor del Parser

## 1. Nuevo parser.py (Estructura Completa)

```python
"""
Módulo de parseo de tickets para GastoTrack.
Extrae información estructurada del texto OCR usando Claude Haiku 3.5.
"""

import re
import json
import logging
from datetime import datetime
from typing import Optional
import anthropic

from gastotrack.config import Config

# Configurar logging
logger = logging.getLogger(__name__)


class LineaProducto:
    """Representa una línea de producto parseada."""

    def __init__(
        self,
        descripcion: str,
        precio: float,
        cantidad_kg: Optional[float] = None,
        precio_por_kg: Optional[float] = None
    ):
        self.descripcion = descripcion.strip()
        self.precio = precio
        self.cantidad_kg = cantidad_kg
        self.precio_por_kg = precio_por_kg

    def __repr__(self):
        if self.cantidad_kg and self.precio_por_kg:
            return (
                f"LineaProducto(descripcion='{self.descripcion}', "
                f"cantidad_kg={self.cantidad_kg}, "
                f"precio_por_kg={self.precio_por_kg}, "
                f"precio={self.precio})"
            )
        return f"LineaProducto(descripcion='{self.descripcion}', precio={self.precio})"


# ============================================================================
# FUNCIONES PARA PARSER CON LLM
# ============================================================================

def crear_prompt_parseo(texto_ocr: str) -> str:
    """
    Crea el prompt para el LLM de Anthropic.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Prompt formateado para el LLM
    """
    return f"""Eres un experto en parsear tickets de supermercado en español.

Tu tarea es extraer información estructurada del siguiente texto OCR de un ticket.

INSTRUCCIONES:
1. Identifica TODOS los productos comprados, incluyendo aquellos cuya descripción está en una línea separada del precio
2. Para productos con peso (kg), extrae:
   - Descripción del producto
   - Cantidad en kg
   - Precio por kg
   - Precio total
3. Para productos normales, extrae:
   - Descripción del producto
   - Precio total
4. Ignora líneas que sean:
   - Totales, subtotales, IVA
   - Información del establecimiento (dirección, teléfono, CIF)
   - Métodos de pago, cambio, tarjeta
   - Números de caja, ticket, operador
   - Promociones o descuentos (líneas con "dto", "ahorro", "promotion")
5. Extrae también:
   - Fecha del ticket (formato YYYY-MM-DD)
   - Nombre del supermercado
   - Total del ticket

IMPORTANTE:
- Si una línea tiene solo texto sin precio, y la siguiente línea tiene información de peso y precio, combínalas en un solo producto
- Los precios siempre usan punto como separador decimal en el JSON (ej: 4.55, no 4,55)
- Las cantidades de peso también usan punto decimal (ej: 1.200, no 1,200)

FORMATO DE SALIDA:
Responde ÚNICAMENTE con un objeto JSON válido con esta estructura:
{{
  "supermercado": "NOMBRE_SUPERMERCADO",
  "fecha": "YYYY-MM-DD",
  "total": 35.19,
  "productos": [
    {{
      "descripcion": "CALABACÍN",
      "cantidad_kg": 1.200,
      "precio_por_kg": 0.245,
      "precio": 0.29
    }},
    {{
      "descripcion": "CHAMPÚ FRUCTIS 360ML FUERZA B",
      "precio": 4.55
    }}
  ]
}}

TEXTO OCR:
{texto_ocr}"""


def validar_respuesta_llm(respuesta: dict) -> bool:
    """
    Valida que la respuesta del LLM tenga la estructura correcta.
    
    Args:
        respuesta: Diccionario con la respuesta del LLM
        
    Returns:
        True si la respuesta es válida, False en caso contrario
    """
    try:
        # Verificar campos obligatorios
        if not isinstance(respuesta, dict):
            return False
        
        if 'productos' not in respuesta:
            return False
        
        if not isinstance(respuesta['productos'], list):
            return False
        
        # Verificar estructura de productos
        for producto in respuesta['productos']:
            if not isinstance(producto, dict):
                return False
            
            if 'descripcion' not in producto or 'precio' not in producto:
                return False
            
            # Si tiene cantidad_kg, debe tener precio_por_kg
            if 'cantidad_kg' in producto and 'precio_por_kg' not in producto:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validando respuesta LLM: {e}")
        return False


def convertir_respuesta_llm(respuesta: dict) -> dict:
    """
    Convierte la respuesta del LLM al formato esperado por la aplicación.
    
    Args:
        respuesta: Diccionario con la respuesta del LLM
        
    Returns:
        Diccionario con el formato esperado
    """
    productos = []
    
    for prod in respuesta.get('productos', []):
        producto = LineaProducto(
            descripcion=prod['descripcion'],
            precio=float(prod['precio']),
            cantidad_kg=float(prod['cantidad_kg']) if 'cantidad_kg' in prod else None,
            precio_por_kg=float(prod['precio_por_kg']) if 'precio_por_kg' in prod else None
        )
        productos.append(producto)
    
    return {
        'productos': productos,
        'total': float(respuesta.get('total', 0.0)),
        'fecha': respuesta.get('fecha', datetime.now().strftime('%Y-%m-%d')),
        'supermercado': respuesta.get('supermercado', 'DESCONOCIDO'),
    }


def parsear_con_llm(texto_ocr: str, max_retries: int = 2) -> dict:
    """
    Parsea el ticket usando Claude Haiku 3.5 de Anthropic.
    
    Args:
        texto_ocr: Texto extraído por OCR
        max_retries: Número máximo de reintentos en caso de error
        
    Returns:
        Diccionario con la información parseada
    """
    if not Config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY no configurada, usando parser regex")
        return parsear_con_regex(texto_ocr)
    
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        prompt = crear_prompt_parseo(texto_ocr)
        
        for intento in range(max_retries):
            try:
                logger.info(f"Llamando a Claude Haiku (intento {intento + 1}/{max_retries})")
                
                message = client.messages.create(
                    model=Config.PARSER_LLM_MODEL,
                    max_tokens=2000,
                    temperature=0,  # Determinístico para parseo
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Extraer texto de la respuesta
                respuesta_texto = message.content[0].text
                logger.debug(f"Respuesta LLM: {respuesta_texto}")
                
                # Parsear JSON
                respuesta_json = json.loads(respuesta_texto)
                
                # Validar estructura
                if validar_respuesta_llm(respuesta_json):
                    logger.info("Parseo con LLM exitoso")
                    return convertir_respuesta_llm(respuesta_json)
                else:
                    logger.warning("Respuesta LLM inválida, reintentando...")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de LLM: {e}")
                if intento == max_retries - 1:
                    logger.warning("Fallback a parser regex")
                    return parsear_con_regex(texto_ocr)
                    
            except anthropic.APIError as e:
                logger.error(f"Error de API de Anthropic: {e}")
                if intento == max_retries - 1:
                    logger.warning("Fallback a parser regex")
                    return parsear_con_regex(texto_ocr)
        
        # Si llegamos aquí, todos los intentos fallaron
        logger.warning("Todos los intentos con LLM fallaron, usando parser regex")
        return parsear_con_regex(texto_ocr)
        
    except Exception as e:
        logger.error(f"Error inesperado en parsear_con_llm: {e}")
        return parsear_con_regex(texto_ocr)


# ============================================================================
# FUNCIONES PARA PARSER CON REGEX (FALLBACK)
# ============================================================================

# Patrones de supermercados conocidos
PATRONES_SUPERMERCADOS = [
    (r'AHORRAMAS', 'AHORRAMAS'),
    (r'ALCAMPO', 'ALCAMPO'),
    (r'ALDI', 'ALDI'),
    (r'CARREFOUR', 'CARREFOUR'),
    (r'CONSUM', 'CONSUM'),
    (r'DIA', 'DIA'),
    (r'EROSKI', 'EROSKI'),
    (r'HIPERCOR', 'HIPERCOR'),
    (r'LIDL', 'LIDL'),
    (r'MERCADONA', 'MERCADONA'),
    (r'SUPERCOR', 'SUPERCOR'),
]

# Palabras clave que indican que una línea NO es un producto
PALABRAS_NO_PRODUCTO = [
    'total', 'subtotal', 'iva', 'cambio', 'tarjeta', 'efectivo',
    'dto', 'descuento', 'ahorro', 'pago', 'importe', 'base',
    'ticket', 'factura', 'gracias', 'vuelva', 'pronto'
]


def normalizar_precio(texto_precio: str) -> Optional[float]:
    """
    Normaliza un texto de precio a float.
    
    Args:
        texto_precio: Texto que contiene un precio (ej: "8,90€", "8.90", "8,90 ")
        
    Returns:
        Precio como float o None si no se puede parsear
    """
    texto = texto_precio.strip().replace('€', '').replace(' ', '')
    texto = texto.replace(',', '.')
    
    try:
        return float(texto)
    except ValueError:
        return None


def extraer_lineas_productos(texto_ocr: str) -> list[LineaProducto]:
    """
    Extrae líneas de productos del texto OCR usando regex.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Lista de LineaProducto
    """
    lineas = texto_ocr.split('\n')
    productos = []
    patron_precio = r'(\d+[.,]\d{2})\s*€?\s*$'
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        match = re.search(patron_precio, linea)
        if not match:
            continue
        
        texto_precio = match.group(1)
        precio = normalizar_precio(texto_precio)
        if precio is None:
            continue
        
        descripcion = linea[:match.start()].strip()
        if not descripcion or len(descripcion) < 3:
            continue
        
        descripcion_lower = descripcion.lower()
        if any(palabra in descripcion_lower for palabra in PALABRAS_NO_PRODUCTO):
            continue
        
        productos.append(LineaProducto(descripcion, precio))
    
    return productos


def detectar_total(texto_ocr: str) -> Optional[float]:
    """Detecta el total del ticket."""
    lineas = texto_ocr.split('\n')
    patron_total = r'total\s*[:\-]?\s*(\d+[.,]\d{2})'
    
    for linea in lineas:
        linea_lower = linea.lower()
        if 'total' in linea_lower:
            match = re.search(patron_total, linea_lower)
            if match:
                precio = normalizar_precio(match.group(1))
                if precio is not None:
                    return precio
    
    productos = extraer_lineas_productos(texto_ocr)
    if productos:
        max_producto = max(p.precio for p in productos)
        for linea in reversed(lineas[-10:]):
            match = re.search(r'(\d+[.,]\d{2})', linea)
            if match:
                precio = normalizar_precio(match.group(1))
                if precio and precio >= max_producto:
                    return precio
    
    return None


def detectar_fecha(texto_ocr: str) -> str:
    """Detecta la fecha del ticket."""
    patrones = [
        r'(\d{2})[/-](\d{2})[/-](\d{4})',
        r'(\d{2})[/-](\d{2})[/-](\d{2})',
    ]
    
    for linea in texto_ocr.split('\n'):
        for patron in patrones:
            match = re.search(patron, linea)
            if match:
                dia, mes, año = match.groups()
                if len(año) == 2:
                    año = f"20{año}"
                try:
                    fecha = datetime(int(año), int(mes), int(dia))
                    return fecha.strftime('%Y-%m-%d')
                except ValueError:
                    continue
    
    return datetime.now().strftime('%Y-%m-%d')


def detectar_supermercado(texto_ocr: str) -> str:
    """Detecta el nombre del supermercado."""
    primeras_lineas = '\n'.join(texto_ocr.split('\n')[:10]).upper()
    
    for patron, nombre in PATRONES_SUPERMERCADOS:
        if re.search(patron, primeras_lineas):
            return nombre
    
    return "DESCONOCIDO"


def parsear_con_regex(texto_ocr: str) -> dict:
    """
    Parsea el ticket usando expresiones regulares (método antiguo).
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Diccionario con la información parseada
    """
    productos = extraer_lineas_productos(texto_ocr)
    total = detectar_total(texto_ocr)
    fecha = detectar_fecha(texto_ocr)
    supermercado = detectar_supermercado(texto_ocr)
    
    if total is None and productos:
        total = sum(p.precio for p in productos)
    
    return {
        'productos': productos,
        'total': total or 0.0,
        'fecha': fecha,
        'supermercado': supermercado,
    }


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def parsear_ticket(texto_ocr: str) -> dict:
    """
    Parsea el texto OCR completo y extrae toda la información del ticket.
    
    Usa LLM si está configurado, o regex como fallback.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Diccionario con la información parseada:
        {
            'productos': list[LineaProducto],
            'total': float,
            'fecha': str,
            'supermercado': str
        }
    """
    if Config.PARSER_USE_LLM:
        logger.info("Usando parser con LLM")
        return parsear_con_llm(texto_ocr)
    else:
        logger.info("Usando parser con regex")
        return parsear_con_regex(texto_ocr)
```

## 2. Actualización de config.py

```python
"""
Módulo de configuración para GastoTrack.
Carga variables de entorno y valida que estén presentes.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()


class Config:
    """Configuración de la aplicación."""

    # Token del bot de Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # API Key de Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Idioma para Tesseract OCR
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "spa")

    # Configuración del parser
    PARSER_USE_LLM: bool = os.getenv("PARSER_USE_LLM", "true").lower() == "true"
    PARSER_LLM_MODEL: str = os.getenv("PARSER_LLM_MODEL", "claude-3-5-haiku-20241022")

    # Rutas
    DB_PATH: str = os.getenv("DB_PATH", "datos/gastotrack.db")
    IMAGES_DIR: str = os.getenv("IMAGES_DIR", "tickets_images")
    CATEGORIES_FILE: str = os.getenv("CATEGORIES_FILE", "datos/categorias.json")

    @classmethod
    def validar(cls) -> None:
        """
        Valida que todas las variables de entorno requeridas estén configuradas.
        Lanza ValueError si falta alguna variable crítica.
        """
        errores = []

        if not cls.TELEGRAM_TOKEN:
            errores.append("TELEGRAM_TOKEN no está configurado en .env")

        if not cls.OCR_LANGUAGE:
            errores.append("OCR_LANGUAGE no está configurado en .env")

        # Validar configuración del parser
        if cls.PARSER_USE_LLM and not cls.ANTHROPIC_API_KEY:
            errores.append(
                "PARSER_USE_LLM está activado pero ANTHROPIC_API_KEY no está configurado. "
                "Configura ANTHROPIC_API_KEY o desactiva PARSER_USE_LLM."
            )

        # Verificar que existan los directorios necesarios
        Path(cls.IMAGES_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

        if errores:
            mensaje = "Errores de configuración:\n" + "\n".join(f"  - {e}" for e in errores)
            raise ValueError(mensaje)

    @classmethod
    def mostrar_config(cls) -> str:
        """Devuelve una representación de la configuración (sin secretos)."""
        return f"""
Configuración de GastoTrack:
  - OCR_LANGUAGE: {cls.OCR_LANGUAGE}
  - DB_PATH: {cls.DB_PATH}
  - IMAGES_DIR: {cls.IMAGES_DIR}
  - CATEGORIES_FILE: {cls.CATEGORIES_FILE}
  - TELEGRAM_TOKEN: {'✓ configurado' if cls.TELEGRAM_TOKEN else '✗ no configurado'}
  - PARSER_USE_LLM: {cls.PARSER_USE_LLM}
  - PARSER_LLM_MODEL: {cls.PARSER_LLM_MODEL}
  - ANTHROPIC_API_KEY: {'✓ configurado' if cls.ANTHROPIC_API_KEY else '✗ no configurado'}
"""
```

## 3. Actualización de .env.example

```bash
# Token del bot de Telegram
# Obtener en: https://t.me/BotFather
TELEGRAM_TOKEN=tu_token_aqui

# API Key de Anthropic para parser con LLM
# Obtener en: https://console.anthropic.com/
ANTHROPIC_API_KEY=tu_api_key_aqui

# Idioma para Tesseract OCR
# Valores comunes: spa (español), eng (inglés)
OCR_LANGUAGE=spa

# Configuración del parser
# true: usar LLM de Anthropic (más preciso, requiere API key)
# false: usar regex tradicional (más rápido, sin costo)
PARSER_USE_LLM=true

# Modelo de Anthropic a usar (solo si PARSER_USE_LLM=true)
# Opciones: claude-3-5-haiku-20241022 (recomendado), claude-3-5-sonnet-20241022
PARSER_LLM_MODEL=claude-3-5-haiku-20241022

# Ruta a la base de datos SQLite
DB_PATH=datos/gastotrack.db

# Ruta al directorio de imágenes de tickets
IMAGES_DIR=tickets_images

# Ruta al archivo de categorías
CATEGORIES_FILE=datos/categorias.json
```

## 4. Actualización de pyproject.toml

```toml
[project]
name = "gastotrack"
version = "0.2.0"
description = "Aplicación personal para registrar tickets de compra mediante Telegram y OCR"
authors = [
    {name = "Tu Nombre", email = "tuemail@ejemplo.com"}
]
readme = "README.md"
requires-python = "^3.12"
dependencies = [
    "python-telegram-bot (>=22.6,<23.0)",
    "pytesseract (>=0.3.13,<0.4.0)",
    "pillow (>=12.1.1,<13.0.0)",
    "streamlit (>=1.54.0,<2.0.0)",
    "plotly (>=6.5.2,<7.0.0)",
    "python-dotenv (>=1.2.1,<2.0.0)",
    "anthropic (>=0.40.0,<1.0.0)"
]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry.group.dev.dependencies]
pytest = "^9.0.2"
pytest-mock = "^3.14.0"
```

## 5. Ejemplo de Test Unitario con Mock

```python
"""
Tests para el módulo parser con LLM.
"""

import pytest
from unittest.mock import patch, MagicMock
from gastotrack.parser import (
    parsear_con_llm,
    parsear_ticket,
    validar_respuesta_llm,
    convertir_respuesta_llm,
    LineaProducto,
)


@pytest.fixture
def mock_anthropic_response():
    """Fixture que simula una respuesta de Anthropic."""
    return {
        "supermercado": "AHORRAMAS",
        "fecha": "2026-02-10",
        "total": 35.19,
        "productos": [
            {
                "descripcion": "CALABACÍN",
                "cantidad_kg": 1.200,
                "precio_por_kg": 0.245,
                "precio": 0.29
            },
            {
                "descripcion": "PLATANO CANARIO BOLSA",
                "cantidad_kg": 0.675,
                "precio_por_kg": 2.29,
                "precio": 1.55
            },
            {
                "descripcion": "CHAMPÚ FRUCTIS 360ML FUERZA B",
                "precio": 4.55
            }
        ]
    }


def test_validar_respuesta_llm_valida(mock_anthropic_response):
    """Test que valida una respuesta correcta del LLM."""
    assert validar_respuesta_llm(mock_anthropic_response) is True


def test_validar_respuesta_llm_invalida():
    """Test que detecta respuestas inválidas."""
    # Sin campo productos
    assert validar_respuesta_llm({"supermercado": "TEST"}) is False
    
    # Productos no es lista
    assert validar_respuesta_llm({"productos": "invalid"}) is False
    
    # Producto sin precio
    assert validar_respuesta_llm({
        "productos": [{"descripcion": "TEST"}]
    }) is False
    
    # Tiene cantidad_kg pero no precio_por_kg
    assert validar_respuesta_llm({
        "productos": [{"descripcion": "TEST", "precio": 1.0, "cantidad_kg": 1.0}]
    }) is False


def test_convertir_respuesta_llm(mock_anthropic_response):
    """Test de conversión de respuesta LLM al formato interno."""
    resultado = convertir_respuesta_llm(mock_anthropic_response)
    
    assert resultado['supermercado'] == "AHORRAMAS"
    assert resultado['fecha'] == "2026-02-10"
    assert resultado['total'] == 35.19
    assert len(resultado['productos']) == 3
    
    # Verificar producto con peso
    producto_peso = resultado['productos'][0]
    assert producto_peso.descripcion == "CALABACÍN"
    assert producto_peso.cantidad_kg == 1.200
    assert producto_peso.precio_por_kg == 0.245
    assert producto_peso.precio == 0.29
    
    # Verificar producto normal
    producto_normal = resultado['productos'][2]
    assert producto_normal.descripcion == "CHAMPÚ FRUCTIS 360ML FUERZA B"
    assert producto_normal.precio == 4.55
    assert producto_normal.cantidad_kg is None
    assert producto_normal.precio_por_kg is None


@patch('anthropic.Anthropic')
def test_parsear_con_llm_exitoso(mock_anthropic_class, mock_anthropic_response):
    """Test de parseo exitoso con LLM."""
    # Configurar mock
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    
    mock_message = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps(mock_anthropic_response)
    mock_message.content = [mock_content]
    mock_client.messages.create.return_value = mock_message
    
    # Ejecutar
    texto_ocr = "AHORRAMAS\nCALABACÍN\n1,200 kg x 0,245 €/kg 0,29€"
    resultado = parsear_con_llm(texto_ocr)
    
    # Verificar
    assert resultado['supermercado'] == "AHORRAMAS"
    assert len(resultado['productos']) == 3
    assert resultado['productos'][0].descripcion == "CALABACÍN"


@patch('anthropic.Anthropic')
def test_parsear_con_llm_fallback_a_regex(mock_anthropic_class):
    """Test que verifica el fallback a regex cuando LLM falla."""
    # Configurar mock para que falle
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.side_effect = Exception("API Error")
    
    # Ejecutar
    texto_ocr = """
MERCADONA
18/02/2026
POLLO PECHUGA 8,90€
LECHE ENTERA 2,10€
TOTAL: 11,00€
"""
    resultado = parsear_con_llm(texto_ocr)
    
    # Verificar que usó regex (debe encontrar productos)
    assert len(resultado['productos']) >= 2
    assert resultado['supermercado'] == "MERCADONA"


def test_parsear_ticket_usa_llm_cuando_configurado():
    """Test que verifica que parsear_ticket usa LLM cuando está configurado."""
    with patch('gastotrack.config.Config.PARSER_USE_LLM', True):
        with patch('gastotrack.parser.parsear_con_llm') as mock_llm:
            mock_llm.return_value = {'productos': [], 'total': 0.0}
            
            parsear_ticket("test")
            
            mock_llm.assert_called_once()


def test_parsear_ticket_usa_regex_cuando_desactivado():
    """Test que verifica que parsear_ticket usa regex cuando LLM está desactivado."""
    with patch('gastotrack.config.Config.PARSER_USE_LLM', False):
        with patch('gastotrack.parser.parsear_con_regex') as mock_regex:
            mock_regex.return_value = {'productos': [], 'total': 0.0}
            
            parsear_ticket("test")
            
            mock_regex.assert_called_once()
```

## 6. Actualización de test_manual.py

```python
def probar_parser(texto_ocr: str):
    """Prueba el módulo parser."""
    imprimir_separador("2. PRUEBA DE PARSER")
    
    # Mostrar configuración del parser
    from gastotrack.config import Config
    print(f"🔧 Configuración del parser:")
    print(f"   - Usar LLM: {Config.PARSER_USE_LLM}")
    if Config.PARSER_USE_LLM:
        print(f"   - Modelo: {Config.PARSER_LLM_MODEL}")
        print(f"   - API Key: {'✓ configurada' if Config.ANTHROPIC_API_KEY else '✗ no configurada'}")
    print()

    resultado = parsear_ticket(texto_ocr)

    print(f"📅 Fecha detectada: {resultado['fecha']}")
    print(f"🏪 Supermercado: {resultado['supermercado']}")
    print(f"💰 Total detectado: {resultado['total']:.2f}€")
    print(f"📦 Productos encontrados: {len(resultado['productos'])}\n")

    if resultado['productos']:
        print("--- PRODUCTOS ---")
        for i, producto in enumerate(resultado['productos'], 1):
            if producto.cantidad_kg and producto.precio_por_kg:
                print(f"{i}. {producto.descripcion:40s}")
                print(f"   ({producto.cantidad_kg:.3f} kg x {producto.precio_por_kg:.2f} €/kg) = {producto.precio:6.2f}€")
            else:
                print(f"{i}. {producto.descripcion:40s} {producto.precio:6.2f}€")
        print("--- FIN PRODUCTOS ---")
    else:
        print("⚠️  No se encontraron productos")

    return resultado
```

## 7. Comando para Instalar Dependencias

```bash
# Instalar la nueva dependencia
poetry add anthropic

# O si usas pip
pip install anthropic>=0.40.0
```

## 8. Ejemplo de Uso

```python
from gastotrack.parser import parsear_ticket

# Texto OCR de ejemplo
texto_ocr = """
AHORRAMAS
LOS URQUIZA, 5-7
28017 - MADRID
10-02-2026 19:44:23

CALABACÍN
1,200 kg x 0,245 €/kg 0,29€

PLATANO CANARIO BOLSA
0,675 kg x 2,29 €/kg 1,55€

CHAMPÚ FRUCTIS 360ML FUERZA B 4,55€

TOTAL: 6,39€
"""

# Parsear
resultado = parsear_ticket(texto_ocr)

# Mostrar resultados
print(f"Supermercado: {resultado['supermercado']}")
print(f"Total: {resultado['total']:.2f}€")
print(f"Productos: {len(resultado['productos'])}")

for producto in resultado['productos']:
    if producto.cantidad_kg:
        print(f"  - {producto.descripcion} ({producto.cantidad_kg} kg x {producto.precio_por_kg} €/kg) = {producto.precio}€")
    else:
        print(f"  - {producto.descripcion} = {producto.precio}€")
```
