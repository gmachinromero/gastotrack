"""
Tests para el módulo parser.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from gastotrack.parser import (
    normalizar_precio,
    extraer_lineas_productos,
    detectar_total,
    detectar_fecha,
    detectar_supermercado,
    parsear_ticket,
    parsear_con_llm,
    parsear_con_regex,
    validar_respuesta_llm,
    convertir_respuesta_llm,
    LineaProducto,
)


# ============================================================================
# TESTS PARA FUNCIONES BÁSICAS (REGEX)
# ============================================================================

def test_normalizar_precio():
    """Test de normalización de precios."""
    assert normalizar_precio("8,90€") == 8.90
    assert normalizar_precio("8.90") == 8.90
    assert normalizar_precio("8,90 ") == 8.90
    assert normalizar_precio("12,50€") == 12.50
    assert normalizar_precio("invalid") is None


def test_extraer_lineas_productos():
    """Test de extracción de líneas de productos."""
    texto_ocr = """
MERCADONA
POLLO PECHUGA 8,90€
LECHE ENTERA 2,10€
TOTAL 11,00€
"""
    productos = extraer_lineas_productos(texto_ocr)

    assert len(productos) == 2
    assert productos[0].descripcion == "POLLO PECHUGA"
    assert productos[0].precio == 8.90
    assert productos[1].descripcion == "LECHE ENTERA"
    assert productos[1].precio == 2.10


def test_extraer_lineas_productos_filtro_no_producto():
    """Test que verifica que se filtran líneas de no-producto."""
    texto_ocr = """
PRODUCTO A 5,00€
TOTAL 10,00€
IVA 2,10€
PRODUCTO B 3,50€
"""
    productos = extraer_lineas_productos(texto_ocr)

    # Solo deben extraerse los productos, no TOTAL ni IVA
    assert len(productos) == 2
    assert productos[0].descripcion == "PRODUCTO A"
    assert productos[1].descripcion == "PRODUCTO B"


def test_detectar_total():
    """Test de detección de total."""
    texto_ocr = """
PRODUCTO A 5,00€
PRODUCTO B 3,50€
TOTAL: 8,50€
"""
    total = detectar_total(texto_ocr)
    assert total == 8.50


def test_detectar_fecha():
    """Test de detección de fecha."""
    texto_ocr = """
MERCADONA
18/02/2026
PRODUCTO A 5,00€
"""
    fecha = detectar_fecha(texto_ocr)
    assert fecha == "2026-02-18"


def test_detectar_fecha_formato_alternativo():
    """Test de detección de fecha con formato alternativo."""
    texto_ocr = """
MERCADONA
18-02-2026
PRODUCTO A 5,00€
"""
    fecha = detectar_fecha(texto_ocr)
    assert fecha == "2026-02-18"


def test_detectar_supermercado():
    """Test de detección de supermercado."""
    texto_ocr = """
MERCADONA S.A.
C/ EJEMPLO 123
18/02/2026
"""
    supermercado = detectar_supermercado(texto_ocr)
    assert supermercado == "MERCADONA"


def test_detectar_supermercado_desconocido():
    """Test de detección de supermercado desconocido."""
    texto_ocr = """
TIENDA DESCONOCIDA
C/ EJEMPLO 123
"""
    supermercado = detectar_supermercado(texto_ocr)
    assert supermercado == "DESCONOCIDO"


def test_parsear_con_regex_completo():
    """Test de parseo completo con regex."""
    texto_ocr = """
MERCADONA
C/ EJEMPLO 123
18/02/2026

POLLO PECHUGA 8,90€
LECHE ENTERA 2,10€
PAN BARRA 1,50€

TOTAL: 12,50€
"""
    resultado = parsear_con_regex(texto_ocr)

    assert resultado['supermercado'] == "MERCADONA"
    assert resultado['fecha'] == "2026-02-18"
    assert resultado['total'] == 12.50
    assert len(resultado['productos']) == 3
    assert resultado['productos'][0].descripcion == "POLLO PECHUGA"
    assert resultado['productos'][0].precio == 8.90


# ============================================================================
# TESTS PARA FUNCIONES LLM
# ============================================================================

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
    
    # Configurar API key
    with patch('gastotrack.parser.Config.ANTHROPIC_API_KEY', 'test_key'):
        # Ejecutar
        texto_ocr = "AHORRAMAS\nCALABACÍN\n1,200 kg x 0,245 €/kg 0,29€"
        resultado = parsear_con_llm(texto_ocr)
        
        # Verificar
        assert resultado['supermercado'] == "AHORRAMAS"
        assert len(resultado['productos']) == 3
        assert resultado['productos'][0].descripcion == "CALABACÍN"
        assert resultado['productos'][0].cantidad_kg == 1.200


@patch('anthropic.Anthropic')
def test_parsear_con_llm_fallback_a_regex(mock_anthropic_class):
    """Test que verifica el fallback a regex cuando LLM falla."""
    # Configurar mock para que falle
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.side_effect = Exception("API Error")
    
    # Configurar API key
    with patch('gastotrack.parser.Config.ANTHROPIC_API_KEY', 'test_key'):
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


def test_parsear_con_llm_sin_api_key():
    """Test que verifica que sin API key usa regex."""
    with patch('gastotrack.parser.Config.ANTHROPIC_API_KEY', ''):
        texto_ocr = """
MERCADONA
18/02/2026
POLLO PECHUGA 8,90€
TOTAL: 8,90€
"""
        resultado = parsear_con_llm(texto_ocr)
        
        # Debe usar regex como fallback
        assert len(resultado['productos']) >= 1
        assert resultado['supermercado'] == "MERCADONA"


def test_parsear_ticket_usa_llm_cuando_configurado():
    """Test que verifica que parsear_ticket usa LLM cuando está configurado."""
    with patch('gastotrack.parser.Config.PARSER_USE_LLM', True):
        with patch('gastotrack.parser.parsear_con_llm') as mock_llm:
            mock_llm.return_value = {
                'productos': [],
                'total': 0.0,
                'fecha': '2026-02-18',
                'supermercado': 'TEST'
            }
            
            parsear_ticket("test")
            
            mock_llm.assert_called_once()


def test_parsear_ticket_usa_regex_cuando_desactivado():
    """Test que verifica que parsear_ticket usa regex cuando LLM está desactivado."""
    with patch('gastotrack.parser.Config.PARSER_USE_LLM', False):
        with patch('gastotrack.parser.parsear_con_regex') as mock_regex:
            mock_regex.return_value = {
                'productos': [],
                'total': 0.0,
                'fecha': '2026-02-18',
                'supermercado': 'TEST'
            }
            
            parsear_ticket("test")
            
            mock_regex.assert_called_once()


# ============================================================================
# TESTS DE INTEGRACIÓN CON PRODUCTOS CON PESO
# ============================================================================

@patch('anthropic.Anthropic')
def test_parsear_producto_con_peso_multilinea(mock_anthropic_class):
    """Test de parseo de producto con peso en múltiples líneas."""
    # Respuesta simulada del LLM
    respuesta_llm = {
        "supermercado": "AHORRAMAS",
        "fecha": "2026-02-10",
        "total": 0.29,
        "productos": [
            {
                "descripcion": "CALABACÍN",
                "cantidad_kg": 1.200,
                "precio_por_kg": 0.245,
                "precio": 0.29
            }
        ]
    }
    
    # Configurar mock
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    
    mock_message = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps(respuesta_llm)
    mock_message.content = [mock_content]
    mock_client.messages.create.return_value = mock_message
    
    # Configurar API key
    with patch('gastotrack.parser.Config.ANTHROPIC_API_KEY', 'test_key'):
        # Texto OCR con producto multi-línea
        texto_ocr = """
AHORRAMAS
10-02-2026

CALABACÍN
1,200 kg x 0,245 €/kg 0,29€

TOTAL: 0,29€
"""
        resultado = parsear_con_llm(texto_ocr)
        
        # Verificar
        assert len(resultado['productos']) == 1
        producto = resultado['productos'][0]
        assert producto.descripcion == "CALABACÍN"
        assert producto.cantidad_kg == 1.200
        assert producto.precio_por_kg == 0.245
        assert producto.precio == 0.29


@patch('anthropic.Anthropic')
def test_parsear_ticket_completo_ahorramas(mock_anthropic_class):
    """Test de parseo completo del ticket de Ahorramas del ejemplo."""
    # Respuesta simulada del LLM con todos los productos
    respuesta_llm = {
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
                "descripcion": "BOQUERON ARTEIÑAKI 70G ALIN",
                "precio": 1.98
            },
            {
                "descripcion": "AGUACATE BANDEJA 450G",
                "precio": 2.59
            },
            {
                "descripcion": "CHAMPÚ FRUCTIS 360ML FUERZA B",
                "precio": 4.55
            }
        ]
    }
    
    # Configurar mock
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    
    mock_message = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps(respuesta_llm)
    mock_message.content = [mock_content]
    mock_client.messages.create.return_value = mock_message
    
    # Configurar API key
    with patch('gastotrack.parser.Config.ANTHROPIC_API_KEY', 'test_key'):
        texto_ocr = """
AHORRAMAS
LOS URQUIZA, 5-7
28017 - MADRID
10-02-2026 19:44:23

CALABACÍN
1,200 kg x 0,245 €/kg 0,29€

PLATANO CANARIO BOLSA
0,675 kg x 2,29 €/kg 1,55€

BOQUERON ARTEIÑAKI 70G ALIN 1,98€
AGUACATE BANDEJA 450G 2,59€
CHAMPÚ FRUCTIS 360ML FUERZA B 4,55€

TOTAL: 35,19€
"""
        resultado = parsear_con_llm(texto_ocr)
        
        # Verificar
        assert resultado['supermercado'] == "AHORRAMAS"
        assert resultado['fecha'] == "2026-02-10"
        assert len(resultado['productos']) == 5
        
        # Verificar productos con peso
        assert resultado['productos'][0].cantidad_kg == 1.200
        assert resultado['productos'][1].cantidad_kg == 0.675
        
        # Verificar productos normales
        assert resultado['productos'][2].cantidad_kg is None
        assert resultado['productos'][3].cantidad_kg is None
        assert resultado['productos'][4].cantidad_kg is None
