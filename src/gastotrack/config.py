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
