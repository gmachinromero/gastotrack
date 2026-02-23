"""
Tests para el módulo clasificador.
"""

import pytest
import json
import tempfile
from pathlib import Path

from gastotrack.clasificador import Clasificador


@pytest.fixture
def archivo_categorias_temporal():
    """Crea un archivo temporal de categorías para testing."""
    categorias = {
        "carne": ["pollo", "ternera", "cerdo"],
        "pescado": ["merluza", "salmon", "atun"],
        "lacteos": ["leche", "yogur", "queso"],
        "bebidas": ["agua", "cerveza", "vino"],
        "verduras": ["tomate", "lechuga", "cebolla", "patata"],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(categorias, f, ensure_ascii=False)
        ruta = f.name

    yield ruta

    # Limpiar
    Path(ruta).unlink(missing_ok=True)


def test_normalizar_texto():
    """Test de normalización de texto."""
    assert Clasificador.normalizar_texto("POLLO PECHUGA 123") == "pollo pechuga"
    assert Clasificador.normalizar_texto("Leche Entera") == "leche entera"
    assert Clasificador.normalizar_texto("Café con Leche") == "cafe con leche"
    assert Clasificador.normalizar_texto("Agua 1.5L") == "agua l"


def test_clasificar_carne(archivo_categorias_temporal):
    """Test de clasificación de productos de carne."""
    clasificador = Clasificador(archivo_categorias_temporal)

    assert clasificador.clasificar("POLLO PECHUGA") == "carne"
    assert clasificador.clasificar("TERNERA FILETE") == "carne"
    assert clasificador.clasificar("CERDO LOMO") == "carne"


def test_clasificar_pescado(archivo_categorias_temporal):
    """Test de clasificación de productos de pescado."""
    clasificador = Clasificador(archivo_categorias_temporal)

    assert clasificador.clasificar("MERLUZA FILETE") == "pescado"
    assert clasificador.clasificar("SALMON AHUMADO") == "pescado"
    assert clasificador.clasificar("ATUN EN LATA") == "pescado"


def test_clasificar_lacteos(archivo_categorias_temporal):
    """Test de clasificación de productos lácteos."""
    clasificador = Clasificador(archivo_categorias_temporal)

    assert clasificador.clasificar("LECHE ENTERA") == "lacteos"
    assert clasificador.clasificar("YOGUR NATURAL") == "lacteos"
    assert clasificador.clasificar("QUESO MANCHEGO") == "lacteos"


def test_clasificar_verduras(archivo_categorias_temporal):
    """Test de clasificación de productos de verduras."""
    clasificador = Clasificador(archivo_categorias_temporal)

    assert clasificador.clasificar("TOMATE RAMA") == "verduras"
    assert clasificador.clasificar("LECHUGA ICEBERG") == "verduras"
    assert clasificador.clasificar("CEBOLLA DULCE") == "verduras"
    assert clasificador.clasificar("PATATA BLANCA") == "verduras"


def test_clasificar_otros(archivo_categorias_temporal):
    """Test de clasificación de productos sin categoría."""
    clasificador = Clasificador(archivo_categorias_temporal)

    assert clasificador.clasificar("PRODUCTO DESCONOCIDO") == "otros"
    assert clasificador.clasificar("ALGO RARO") == "otros"


def test_aprender_categoria(archivo_categorias_temporal):
    """Test de aprendizaje de nueva categoría."""
    clasificador = Clasificador(archivo_categorias_temporal)

    # Inicialmente no clasifica correctamente
    assert clasificador.clasificar("MANZANA GOLDEN") == "otros"

    # Aprender nueva categoría
    clasificador.aprender_categoria("MANZANA GOLDEN", "frutas")

    # Recargar clasificador
    clasificador_nuevo = Clasificador(archivo_categorias_temporal)

    # Ahora debería clasificar correctamente
    assert clasificador_nuevo.clasificar("MANZANA GOLDEN") == "frutas"
    assert clasificador_nuevo.clasificar("MANZANA ROJA") == "frutas"


def test_obtener_categorias_disponibles(archivo_categorias_temporal):
    """Test de obtención de categorías disponibles."""
    clasificador = Clasificador(archivo_categorias_temporal)

    categorias = clasificador.obtener_categorias_disponibles()

    assert "carne" in categorias
    assert "pescado" in categorias
    assert "lacteos" in categorias
    assert "bebidas" in categorias
    assert "verduras" in categorias


def test_obtener_palabras_clave(archivo_categorias_temporal):
    """Test de obtención de palabras clave de una categoría."""
    clasificador = Clasificador(archivo_categorias_temporal)

    palabras_carne = clasificador.obtener_palabras_clave("carne")
    assert "pollo" in palabras_carne
    assert "ternera" in palabras_carne
    assert "cerdo" in palabras_carne

    palabras_verduras = clasificador.obtener_palabras_clave("verduras")
    assert "tomate" in palabras_verduras
    assert "lechuga" in palabras_verduras
    assert "cebolla" in palabras_verduras
    assert "patata" in palabras_verduras


def test_archivo_no_existe():
    """Test que verifica que se lanza error si el archivo no existe."""
    with pytest.raises(FileNotFoundError):
        Clasificador("/ruta/inexistente/categorias.json")
