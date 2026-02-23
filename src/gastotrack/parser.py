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
    """
    Detecta el total del ticket.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Total como float o None si no se encuentra
    """
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
    """
    Detecta la fecha del ticket.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Fecha en formato YYYY-MM-DD o fecha actual si no se encuentra
    """
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
    """
    Detecta el nombre del supermercado.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Nombre del supermercado o "DESCONOCIDO" si no se encuentra
    """
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
