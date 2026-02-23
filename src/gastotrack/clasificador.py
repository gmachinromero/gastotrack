"""
Módulo de clasificación de productos para GastoTrack.
Clasifica productos en categorías basándose en palabras clave.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

from gastotrack.config import Config


class Clasificador:
    """Clasifica productos en categorías usando un diccionario de palabras clave."""

    def __init__(self, ruta_categorias: Optional[str] = None):
        """
        Inicializa el clasificador.

        Args:
            ruta_categorias: Ruta al archivo JSON de categorías.
                           Si es None, usa Config.CATEGORIES_FILE

        Raises:
            FileNotFoundError: Si el archivo de categorías no existe
        """
        self.ruta_categorias = ruta_categorias or Config.CATEGORIES_FILE
        self.categorias = self._cargar_categorias()

    def _cargar_categorias(self) -> dict[str, list[str]]:
        """
        Carga el diccionario de categorías desde el archivo JSON.

        Returns:
            Diccionario con categorías y sus palabras clave

        Raises:
            FileNotFoundError: Si el archivo no existe
        """
        ruta = Path(self.ruta_categorias)

        if not ruta.exists():
            raise FileNotFoundError(
                f"El archivo de categorías no existe: {self.ruta_categorias}\n"
                f"Asegúrate de que existe el archivo datos/categorias.json"
            )

        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _guardar_categorias(self, categorias: dict[str, list[str]]) -> None:
        """
        Guarda el diccionario de categorías en el archivo JSON.

        Args:
            categorias: Diccionario de categorías a guardar
        """
        ruta = Path(self.ruta_categorias)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(categorias, f, ensure_ascii=False, indent=2)

    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """
        Normaliza un texto para facilitar la comparación.

        Args:
            texto: Texto a normalizar

        Returns:
            Texto normalizado (minúsculas, sin acentos, sin números)
        """
        # Convertir a minúsculas
        texto = texto.lower()

        # Eliminar acentos
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )

        # Eliminar números y caracteres especiales, mantener solo letras y espacios
        texto = re.sub(r'[^a-z\s]', '', texto)

        # Eliminar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto).strip()

        return texto

    def clasificar(self, descripcion: str) -> str:
        """
        Clasifica un producto en una categoría.

        Args:
            descripcion: Descripción del producto

        Returns:
            Nombre de la categoría o "otros" si no se encuentra match
        """
        descripcion_normalizada = self.normalizar_texto(descripcion)

        # Recorrer cada categoría y sus palabras clave
        for categoria, palabras_clave in self.categorias.items():
            for palabra in palabras_clave:
                palabra_normalizada = self.normalizar_texto(palabra)

                # Buscar match parcial (la palabra clave está contenida en la descripción)
                if palabra_normalizada in descripcion_normalizada:
                    return categoria

        return "otros"

    def aprender_categoria(self, descripcion: str, categoria: str) -> None:
        """
        Añade una palabra clave a una categoría basándose en una corrección del usuario.

        Args:
            descripcion: Descripción del producto
            categoria: Categoría correcta
        """
        # Normalizar descripción
        descripcion_normalizada = self.normalizar_texto(descripcion)

        # Extraer la palabra más representativa (la más larga)
        palabras = descripcion_normalizada.split()
        if not palabras:
            return

        # Filtrar palabras muy cortas (artículos, preposiciones, etc.)
        palabras_validas = [p for p in palabras if len(p) > 3]

        if not palabras_validas:
            # Si no hay palabras válidas, usar la más larga de todas
            palabra_clave = max(palabras, key=len)
        else:
            # Usar la palabra válida más larga
            palabra_clave = max(palabras_validas, key=len)

        # Añadir a la categoría si no existe
        if categoria not in self.categorias:
            self.categorias[categoria] = []

        if palabra_clave not in self.categorias[categoria]:
            self.categorias[categoria].append(palabra_clave)
            self._guardar_categorias(self.categorias)

    def obtener_categorias_disponibles(self) -> list[str]:
        """
        Obtiene la lista de categorías disponibles.

        Returns:
            Lista de nombres de categorías
        """
        return list(self.categorias.keys())

    def obtener_palabras_clave(self, categoria: str) -> list[str]:
        """
        Obtiene las palabras clave de una categoría.

        Args:
            categoria: Nombre de la categoría

        Returns:
            Lista de palabras clave o lista vacía si la categoría no existe
        """
        return self.categorias.get(categoria, [])
