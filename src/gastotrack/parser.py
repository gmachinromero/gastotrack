"""
Módulo de parseo de tickets para GastoTrack.
Extrae información estructurada del texto OCR usando Claude Haiku exclusivamente.
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


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class ParserError(Exception):
    """Error durante el parseo del ticket."""
    pass


class ParserConfigError(Exception):
    """Error de configuración del parser."""
    pass


# ============================================================================
# CONSTANTES
# ============================================================================

# Patrones de supermercados conocidos (usados en el prompt del LLM)
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


# ============================================================================
# CLASE DE DATOS
# ============================================================================

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
# FUNCIONES DE PROMPT
# ============================================================================

def crear_prompt_parseo(texto_ocr: str) -> str:
    """
    Crea el prompt para el LLM de Anthropic.
    
    Args:
        texto_ocr: Texto extraído por OCR
        
    Returns:
        Prompt formateado para el LLM
    """
    # Extraer nombres de supermercados conocidos
    supermercados_conocidos = ", ".join([nombre for _, nombre in PATRONES_SUPERMERCADOS])
    
    return f"""Eres un experto en parsear tickets de supermercado en español.

Tu tarea es extraer información estructurada del siguiente texto OCR de un ticket.

SUPERMERCADOS CONOCIDOS EN ESPAÑA:
{supermercados_conocidos}

Si detectas alguno de estos nombres en el ticket, úsalo exactamente como aparece en la lista anterior.
Si no reconoces el supermercado, intenta extraer el nombre de las primeras líneas del ticket.

INSTRUCCIONES:
1. Identifica TODOS los productos comprados, incluyendo aquellos cuya descripción está en una línea separada del precio
2. Para productos con peso (kg), extrae:
   - Descripción del producto
   - Cantidad en kg
   - Precio por kg (€/kg)
   - Precio total
3. Para productos normales, extrae:
   - Descripción del producto
   - Precio total
4. Ignora líneas que sean:
   - Totales, subtotales, IVA
   - Información del establecimiento (dirección, teléfono, CIF)
   - Métodos de pago, cambio, tarjeta
   - Números de caja, ticket, operador
   - Promociones o descuentos (líneas con "dto", "ahorro", "promotion", "PROMOCION")
5. Extrae también:
   - Fecha del ticket (formato YYYY-MM-DD)
   - Nombre del supermercado
   - Total del ticket

IMPORTANTE:
- Si una línea tiene solo texto sin precio, y la siguiente línea tiene información de peso y precio, combínalas en un solo producto
- Los precios siempre usan punto como separador decimal en el JSON (ej: 4.55, no 4,55)
- Las cantidades de peso también usan punto decimal (ej: 1.200, no 1,200)

FORMATO DE SALIDA:
Responde ÚNICAMENTE con un objeto JSON válido. NO incluyas texto explicativo antes o después del JSON.
NO uses bloques de código markdown (```json). El JSON debe empezar directamente con {{ y terminar con }}.

Estructura del JSON:
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


# ============================================================================
# FUNCIONES DE EXTRACCIÓN
# ============================================================================

def extraer_json_de_respuesta(respuesta_texto: str) -> dict:
    """
    Extrae JSON de la respuesta del LLM, manejando casos donde
    hay texto adicional antes/después del JSON.
    
    Args:
        respuesta_texto: Texto de respuesta del LLM
        
    Returns:
        Diccionario parseado del JSON
        
    Raises:
        json.JSONDecodeError: Si no se encuentra JSON válido
    """
    texto = respuesta_texto.strip()
    
    # Caso 1: Respuesta limpia (ideal)
    if texto.startswith('{') and texto.endswith('}'):
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            pass  # Intentar otros métodos
    
    # Caso 2: Respuesta con markdown ```json
    if '```json' in texto:
        inicio = texto.find('```json') + 7
        fin = texto.find('```', inicio)
        if fin != -1:
            json_texto = texto[inicio:fin].strip()
            try:
                return json.loads(json_texto)
            except json.JSONDecodeError:
                pass
    
    # Caso 3: Respuesta con markdown ``` sin especificar json
    if '```' in texto:
        inicio = texto.find('```') + 3
        fin = texto.find('```', inicio)
        if fin != -1:
            json_texto = texto[inicio:fin].strip()
            try:
                return json.loads(json_texto)
            except json.JSONDecodeError:
                pass
    
    # Caso 4: Buscar el primer { y último }
    inicio = texto.find('{')
    fin = texto.rfind('}')
    if inicio != -1 and fin != -1 and inicio < fin:
        json_texto = texto[inicio:fin+1]
        try:
            return json.loads(json_texto)
        except json.JSONDecodeError:
            pass
    
    # Si no se encuentra JSON válido
    raise json.JSONDecodeError(
        "No se encontró JSON válido en la respuesta del LLM",
        texto, 0
    )


# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validar_respuesta_llm(respuesta: dict) -> tuple[bool, str]:
    """
    Valida que la respuesta del LLM tenga la estructura correcta.
    
    Args:
        respuesta: Diccionario con la respuesta del LLM
        
    Returns:
        Tupla (válido, mensaje_error)
    """
    try:
        # Verificar que sea un diccionario
        if not isinstance(respuesta, dict):
            return False, "La respuesta no es un diccionario"
        
        # Verificar campos obligatorios
        campos_requeridos = ['productos', 'supermercado', 'fecha', 'total']
        for campo in campos_requeridos:
            if campo not in respuesta:
                return False, f"Falta el campo obligatorio: {campo}"
        
        # Verificar que productos sea una lista
        if not isinstance(respuesta['productos'], list):
            return False, "El campo 'productos' debe ser una lista"
        
        # Verificar que haya al menos un producto
        if len(respuesta['productos']) == 0:
            return False, "No se encontraron productos en el ticket"
        
        # Verificar estructura de cada producto
        for i, producto in enumerate(respuesta['productos']):
            if not isinstance(producto, dict):
                return False, f"Producto {i+1} no es un diccionario"
            
            if 'descripcion' not in producto:
                return False, f"Producto {i+1} no tiene descripción"
            
            if 'precio' not in producto:
                return False, f"Producto {i+1} no tiene precio"
            
            # Validar coherencia de productos con peso
            if 'cantidad_kg' in producto:
                if 'precio_por_kg' not in producto:
                    return False, f"Producto {i+1} tiene cantidad_kg pero no precio_por_kg"
        
        # Validar tipos de datos numéricos
        try:
            float(respuesta['total'])
        except (ValueError, TypeError):
            return False, f"El total no es un número válido: {respuesta['total']}"
        
        # Validar formato de fecha
        try:
            datetime.strptime(respuesta['fecha'], '%Y-%m-%d')
        except (ValueError, TypeError):
            return False, f"La fecha no tiene formato válido (YYYY-MM-DD): {respuesta['fecha']}"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validando respuesta LLM: {e}")
        return False, f"Error inesperado en validación: {e}"


# ============================================================================
# FUNCIONES DE CONVERSIÓN
# ============================================================================

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


# ============================================================================
# FUNCIÓN PRINCIPAL DE PARSEO
# ============================================================================

def parsear_con_llm(texto_ocr: str, max_retries: int = 3) -> dict:
    """
    Parsea el ticket usando un llm
    
    Args:
        texto_ocr: Texto extraído por OCR
        max_retries: Número máximo de reintentos en caso de error
        
    Returns:
        Diccionario con la información parseada:
        {
            'productos': list[LineaProducto],
            'total': float,
            'fecha': str,
            'supermercado': str
        }
        
    Raises:
        ParserConfigError: Si no está configurada la API key
        ParserError: Si no se puede parsear el ticket después de los reintentos
    """
    # Validar configuración
    if not Config.ANTHROPIC_API_KEY:
        raise ParserConfigError(
            "ANTHROPIC_API_KEY no está configurada. "
            "Configura la variable de entorno para usar el parser con LLM."
        )
    
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        prompt = crear_prompt_parseo(texto_ocr)
        
        ultimo_error = None
        
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
                logger.debug(f"Respuesta LLM (intento {intento + 1}):\n{respuesta_texto[:500]}...")
                
                # Extraer JSON (maneja casos con texto adicional)
                respuesta_json = extraer_json_de_respuesta(respuesta_texto)
                logger.debug(f"JSON extraído: {json.dumps(respuesta_json, indent=2, ensure_ascii=False)}")
                
                # Validar estructura
                valido, mensaje_error = validar_respuesta_llm(respuesta_json)
                if not valido:
                    logger.warning(f"Respuesta LLM inválida (intento {intento + 1}): {mensaje_error}")
                    ultimo_error = mensaje_error
                    continue
                
                # Convertir y retornar
                logger.info("✅ Parseo con LLM exitoso")
                return convertir_respuesta_llm(respuesta_json)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON (intento {intento + 1}): {e}")
                logger.debug(f"Respuesta que causó el error:\n{respuesta_texto}")
                ultimo_error = f"JSON inválido: {e}"
                
            except anthropic.APIError as e:
                logger.error(f"Error de API de Anthropic (intento {intento + 1}): {e}")
                ultimo_error = f"Error de API: {e}"
                
            except Exception as e:
                logger.error(f"Error inesperado (intento {intento + 1}): {e}")
                ultimo_error = f"Error inesperado: {e}"
        
        # Si llegamos aquí, todos los intentos fallaron
        raise ParserError(
            f"No se pudo parsear el ticket después de {max_retries} intentos. "
            f"Último error: {ultimo_error}"
        )
        
    except anthropic.APIError as e:
        raise ParserError(f"Error de API de Anthropic: {e}")
    except Exception as e:
        if isinstance(e, (ParserError, ParserConfigError)):
            raise
        raise ParserError(f"Error inesperado en parsear_con_llm: {e}")


# ============================================================================
# FUNCIÓN PÚBLICA
# ============================================================================

def parsear_ticket(texto_ocr: str) -> dict:
    """
    Parsea el texto OCR completo y extrae toda la información del ticket.
    
    Usa exclusivamente Claude Haiku (LLM) para el parseo.
    
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
        
    Raises:
        ParserConfigError: Si no está configurada la API key
        ParserError: Si no se puede parsear el ticket
    """
    return parsear_con_llm(texto_ocr)
