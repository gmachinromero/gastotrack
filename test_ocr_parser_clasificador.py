#!/usr/bin/env python3
"""
Script de prueba manual para GastoTrack.
Permite probar OCR, parser y clasificador con una imagen de ticket.

Uso:
    poetry run python test_manual.py <ruta_imagen>

Ejemplo:
    poetry run python test_manual.py test_data/ticket_ejemplo.jpg
"""

import sys
from pathlib import Path

# Añadir src al path para poder importar gastotrack
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gastotrack.ocr import extraer_texto, OCRError, verificar_tesseract
from gastotrack.parser import parsear_ticket
from gastotrack.clasificador import Clasificador
from gastotrack.modelos import Ticket, DetalleTicket


def imprimir_separador(titulo: str):
    """Imprime un separador visual."""
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}\n")


def probar_ocr(ruta_imagen: str):
    """Prueba el módulo OCR."""
    imprimir_separador("1. PRUEBA DE OCR")

    # Verificar Tesseract
    if not verificar_tesseract():
        print("❌ ERROR: Tesseract no está instalado o no se encuentra.")
        print("   Instalar con: sudo apt install tesseract-ocr tesseract-ocr-spa")
        return None

    print("✅ Tesseract encontrado")

    # Extraer texto
    try:
        print(f"📄 Procesando imagen: {ruta_imagen}")
        texto_ocr = extraer_texto(ruta_imagen)
        print(f"✅ Texto extraído ({len(texto_ocr)} caracteres)\n")
        print("--- TEXTO OCR ---")
        print(texto_ocr)
        print("--- FIN TEXTO OCR ---")
        return texto_ocr
    except OCRError as e:
        print(f"❌ Error de OCR: {e}")
        return None


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


def probar_clasificador(resultado_parser: dict):
    """Prueba el módulo clasificador."""
    imprimir_separador("3. PRUEBA DE CLASIFICADOR")

    try:
        clasificador = Clasificador()
        print("✅ Clasificador cargado")
        print(f"📚 Categorías disponibles: {', '.join(clasificador.obtener_categorias_disponibles())}\n")

        if not resultado_parser['productos']:
            print("⚠️  No hay productos para clasificar")
            return []

        print("--- CLASIFICACIÓN ---")
        detalles = []
        for i, producto in enumerate(resultado_parser['productos'], 1):
            categoria = clasificador.clasificar(producto.descripcion)
            descripcion_norm = clasificador.normalizar_texto(producto.descripcion)

            detalle = DetalleTicket(
                descripcion_original=producto.descripcion,
                descripcion_normalizada=descripcion_norm,
                categoria=categoria,
                precio_detectado=producto.precio,
            )
            detalles.append(detalle)

            print(f"{i}. {producto.descripcion:40s} → {categoria:15s} ({producto.precio:.2f}€)")

        print("--- FIN CLASIFICACIÓN ---")
        return detalles

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("   Asegúrate de que existe el archivo datos/categorias.json")
        return []


def crear_ticket_completo(ruta_imagen: str, resultado_parser: dict, detalles: list):
    """Crea un objeto Ticket completo."""
    imprimir_separador("4. TICKET COMPLETO")

    import hashlib
    with open(ruta_imagen, 'rb') as f:
        hash_imagen = hashlib.sha256(f.read()).hexdigest()

    ticket = Ticket(
        fecha=resultado_parser['fecha'],
        supermercado=resultado_parser['supermercado'],
        total_detectado=resultado_parser['total'],
        ruta_imagen=ruta_imagen,
        texto_ocr="[texto OCR completo]",
        hash_imagen=hash_imagen[:16],  # Solo primeros 16 caracteres para visualización
        detalles=detalles,
    )

    print(ticket.resumen_telegram())

    return ticket


def main():
    """Función principal."""
    print("\n🧾 GastoTrack - Prueba Manual\n")

    # Verificar argumentos
    if len(sys.argv) < 2:
        print("❌ Error: Debes proporcionar la ruta a una imagen de ticket")
        print(f"\nUso: poetry run python {sys.argv[0]} <ruta_imagen>")
        print(f"Ejemplo: poetry run python {sys.argv[0]} test_data/ticket_ejemplo.jpg")
        sys.exit(1)

    ruta_imagen = sys.argv[1]

    # Verificar que existe la imagen
    if not Path(ruta_imagen).exists():
        print(f"❌ Error: La imagen no existe: {ruta_imagen}")
        sys.exit(1)

    print(f"📸 Imagen: {ruta_imagen}\n")

    # 1. Probar OCR
    texto_ocr = probar_ocr(ruta_imagen)
    if not texto_ocr:
        print("\n❌ No se pudo continuar sin texto OCR")
        sys.exit(1)

    # 2. Probar Parser
    resultado_parser = probar_parser(texto_ocr)

    # 3. Probar Clasificador
    detalles = probar_clasificador(resultado_parser)

    # 4. Crear ticket completo
    if detalles:
        ticket = crear_ticket_completo(ruta_imagen, resultado_parser, detalles)

        # Resumen final
        imprimir_separador("RESUMEN FINAL")
        print(f"✅ Procesamiento completado")
        print(f"   - Productos detectados: {len(resultado_parser['productos'])}")
        print(f"   - Productos clasificados: {len(detalles)}")
        print(f"   - Total: {resultado_parser['total']:.2f}€")
        print(f"   - Supermercado: {resultado_parser['supermercado']}")
        print(f"   - Fecha: {resultado_parser['fecha']}")

        # Distribución por categoría
        categorias_count = {}
        for detalle in detalles:
            categorias_count[detalle.categoria] = categorias_count.get(detalle.categoria, 0) + 1

        print(f"\n📊 Distribución por categoría:")
        for cat, count in sorted(categorias_count.items()):
            print(f"   - {cat.capitalize()}: {count} producto(s)")

    print("\n✅ Prueba completada\n")


if __name__ == '__main__':
    main()
