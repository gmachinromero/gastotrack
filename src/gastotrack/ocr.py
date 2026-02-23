"""
Módulo de OCR para GastoTrack.
Procesa imágenes de tickets con Tesseract.
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
from typing import Optional

from gastotrack.config import Config


class OCRError(Exception):
    """Excepción personalizada para errores de OCR."""
    pass


def preprocesar_imagen(ruta_imagen: str) -> Image.Image:
    """
    Preprocesa la imagen para mejorar la calidad del OCR.

    Args:
        ruta_imagen: Ruta a la imagen

    Returns:
        Imagen preprocesada

    Raises:
        OCRError: Si hay un error al cargar la imagen
    """
    try:
        imagen = Image.open(ruta_imagen)

        # Convertir a escala de grises
        imagen = imagen.convert('L')

        # Aumentar contraste
        enhancer = ImageEnhance.Contrast(imagen)
        imagen = enhancer.enhance(2.0)

        # Aumentar nitidez
        imagen = imagen.filter(ImageFilter.SHARPEN)

        # Redimensionar si es muy pequeña (mínimo 1000px de ancho)
        ancho, alto = imagen.size
        if ancho < 1000:
            factor = 1000 / ancho
            nuevo_ancho = int(ancho * factor)
            nuevo_alto = int(alto * factor)
            imagen = imagen.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)

        return imagen

    except Exception as e:
        raise OCRError(f"Error al preprocesar imagen: {e}")


def extraer_texto(ruta_imagen: str, idioma: Optional[str] = None) -> str:
    """
    Extrae texto de una imagen usando Tesseract OCR.

    Args:
        ruta_imagen: Ruta a la imagen
        idioma: Código de idioma para Tesseract (por defecto usa Config.OCR_LANGUAGE)

    Returns:
        Texto extraído de la imagen

    Raises:
        OCRError: Si hay un error durante el proceso de OCR
    """
    if not Path(ruta_imagen).exists():
        raise OCRError(f"La imagen no existe: {ruta_imagen}")

    idioma = idioma or Config.OCR_LANGUAGE

    try:
        # Preprocesar imagen
        imagen = preprocesar_imagen(ruta_imagen)

        # Configuración de Tesseract
        config_tesseract = '--psm 6'  # PSM 6: Asume un bloque uniforme de texto

        # Ejecutar OCR
        texto = pytesseract.image_to_string(
            imagen,
            lang=idioma,
            config=config_tesseract
        )

        if not texto.strip():
            raise OCRError("No se pudo extraer texto de la imagen")

        return texto

    except pytesseract.TesseractNotFoundError:
        raise OCRError(
            "Tesseract no está instalado o no se encuentra en el PATH. "
            "Instalar con: sudo apt install tesseract-ocr tesseract-ocr-spa"
        )
    except Exception as e:
        raise OCRError(f"Error durante el OCR: {e}")


def verificar_tesseract() -> bool:
    """
    Verifica que Tesseract esté instalado y funcional.

    Returns:
        True si Tesseract está disponible, False en caso contrario
    """
    try:
        version = pytesseract.get_tesseract_version()
        return True
    except:
        return False


def obtener_version_tesseract() -> str:
    """
    Obtiene la versión de Tesseract instalada.

    Returns:
        String con la versión o mensaje de error
    """
    try:
        version = pytesseract.get_tesseract_version()
        return f"Tesseract {version}"
    except:
        return "Tesseract no encontrado"
