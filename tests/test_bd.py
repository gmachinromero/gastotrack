"""
Tests para el módulo de base de datos.
"""

import pytest
import tempfile
from pathlib import Path

from gastotrack.bd import BaseDatos
from gastotrack.modelos import Ticket, DetalleTicket


@pytest.fixture
def bd_temporal():
    """Crea una base de datos temporal para testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        ruta = f.name

    bd = BaseDatos(ruta)
    yield bd
    bd.cerrar()

    # Limpiar
    Path(ruta).unlink(missing_ok=True)


def test_crear_tablas(bd_temporal):
    """Test que verifica que las tablas se crean correctamente."""
    cursor = bd_temporal.conn.cursor()

    # Verificar que existe la tabla ticket
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticket'")
    assert cursor.fetchone() is not None

    # Verificar que existe la tabla detalle_ticket
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detalle_ticket'")
    assert cursor.fetchone() is not None


def test_insertar_ticket(bd_temporal):
    """Test de inserción de ticket."""
    # Crear ticket de prueba
    detalles = [
        DetalleTicket(
            descripcion_original="POLLO PECHUGA",
            descripcion_normalizada="pollo pechuga",
            categoria="carne",
            precio_detectado=8.90,
        ),
        DetalleTicket(
            descripcion_original="LECHE ENTERA",
            descripcion_normalizada="leche entera",
            categoria="lacteos",
            precio_detectado=2.10,
        ),
    ]

    ticket = Ticket(
        fecha="2026-02-18",
        supermercado="MERCADONA",
        total_detectado=11.00,
        ruta_imagen="test.jpg",
        texto_ocr="texto de prueba",
        hash_imagen="abc123",
        detalles=detalles,
    )

    # Insertar ticket
    ticket_id = bd_temporal.insertar_ticket(ticket)

    assert ticket_id > 0


def test_obtener_ticket(bd_temporal):
    """Test de obtención de ticket por ID."""
    # Crear e insertar ticket
    detalles = [
        DetalleTicket(
            descripcion_original="PRODUCTO A",
            descripcion_normalizada="producto a",
            categoria="otros",
            precio_detectado=5.00,
        ),
    ]

    ticket = Ticket(
        fecha="2026-02-18",
        supermercado="MERCADONA",
        total_detectado=5.00,
        ruta_imagen="test.jpg",
        texto_ocr="texto",
        hash_imagen="hash123",
        detalles=detalles,
    )

    ticket_id = bd_temporal.insertar_ticket(ticket)

    # Obtener ticket
    ticket_obtenido = bd_temporal.obtener_ticket(ticket_id)

    assert ticket_obtenido is not None
    assert ticket_obtenido.id == ticket_id
    assert ticket_obtenido.fecha == "2026-02-18"
    assert ticket_obtenido.supermercado == "MERCADONA"
    assert len(ticket_obtenido.detalles) == 1
    assert ticket_obtenido.detalles[0].descripcion_original == "PRODUCTO A"


def test_existe_ticket_por_hash(bd_temporal):
    """Test de detección de duplicados por hash."""
    # Insertar ticket
    ticket = Ticket(
        fecha="2026-02-18",
        supermercado="MERCADONA",
        total_detectado=10.00,
        ruta_imagen="test.jpg",
        texto_ocr="texto",
        hash_imagen="hash_unico",
        detalles=[],
    )

    bd_temporal.insertar_ticket(ticket)

    # Verificar que existe
    assert bd_temporal.existe_ticket_por_hash("hash_unico") is True
    assert bd_temporal.existe_ticket_por_hash("hash_inexistente") is False


def test_existe_ticket_por_datos(bd_temporal):
    """Test de detección de duplicados por datos."""
    # Insertar ticket
    ticket = Ticket(
        fecha="2026-02-18",
        supermercado="MERCADONA",
        total_detectado=10.00,
        ruta_imagen="test.jpg",
        texto_ocr="texto",
        hash_imagen="hash1",
        detalles=[],
    )

    bd_temporal.insertar_ticket(ticket)

    # Verificar que existe
    assert bd_temporal.existe_ticket_por_datos("2026-02-18", 10.00, "MERCADONA") is True
    assert bd_temporal.existe_ticket_por_datos("2026-02-19", 10.00, "MERCADONA") is False
    assert bd_temporal.existe_ticket_por_datos("2026-02-18", 15.00, "MERCADONA") is False


def test_obtener_estadisticas_basicas(bd_temporal):
    """Test de obtención de estadísticas básicas."""
    # Insertar varios tickets
    for i in range(3):
        detalles = [
            DetalleTicket(
                descripcion_original=f"PRODUCTO {i}",
                descripcion_normalizada=f"producto {i}",
                categoria="carne",
                precio_detectado=10.00,
            ),
        ]

        ticket = Ticket(
            fecha=f"2026-02-{18+i:02d}",
            supermercado="MERCADONA",
            total_detectado=10.00,
            ruta_imagen=f"test{i}.jpg",
            texto_ocr="texto",
            hash_imagen=f"hash{i}",
            detalles=detalles,
        )

        bd_temporal.insertar_ticket(ticket)

    # Obtener estadísticas
    stats = bd_temporal.obtener_estadisticas_basicas()

    assert stats['num_tickets'] == 3
    assert stats['total_gastado'] == 30.00
    assert 'carne' in stats['gasto_por_categoria']
    assert stats['gasto_por_categoria']['carne'] == 30.00
    assert 'MERCADONA' in stats['gasto_por_supermercado']
    assert stats['gasto_por_supermercado']['MERCADONA'] == 30.00


def test_context_manager(bd_temporal):
    """Test del context manager."""
    ruta = bd_temporal.ruta_bd
    bd_temporal.cerrar()

    # Usar context manager
    with BaseDatos(ruta) as bd:
        assert bd.conn is not None

    # La conexión debe estar cerrada después del with
    # (no podemos verificar esto directamente, pero no debe lanzar error)
