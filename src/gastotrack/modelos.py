"""
Modelos de datos para GastoTrack.
Define las estructuras de Ticket y DetalleTicket.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DetalleTicket:
    """Representa una línea de producto en un ticket."""

    descripcion_original: str
    descripcion_normalizada: str
    categoria: str
    precio_detectado: float
    precio_confirmado: Optional[float] = None
    eliminado: bool = False
    id: Optional[int] = None
    ticket_id: Optional[int] = None

    def __post_init__(self):
        """Inicializa precio_confirmado si no está definido."""
        if self.precio_confirmado is None:
            self.precio_confirmado = self.precio_detectado

    def precio_final(self) -> float:
        """Devuelve el precio confirmado o detectado."""
        return self.precio_confirmado if self.precio_confirmado is not None else self.precio_detectado

    def to_dict(self) -> dict:
        """Convierte el detalle a diccionario."""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "descripcion_original": self.descripcion_original,
            "descripcion_normalizada": self.descripcion_normalizada,
            "categoria": self.categoria,
            "precio_detectado": self.precio_detectado,
            "precio_confirmado": self.precio_confirmado,
            "eliminado": 1 if self.eliminado else 0,
        }


@dataclass
class Ticket:
    """Representa un ticket de compra completo."""

    fecha: str  # Formato: YYYY-MM-DD
    supermercado: str
    total_detectado: float
    ruta_imagen: str
    texto_ocr: str
    hash_imagen: str
    total_confirmado: Optional[float] = None
    created_at: Optional[str] = None
    id: Optional[int] = None
    detalles: list[DetalleTicket] = field(default_factory=list)

    def __post_init__(self):
        """Inicializa valores por defecto."""
        if self.total_confirmado is None:
            self.total_confirmado = self.total_detectado
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def total_final(self) -> float:
        """Devuelve el total confirmado o detectado."""
        return self.total_confirmado if self.total_confirmado is not None else self.total_detectado

    def calcular_total_detalles(self) -> float:
        """Calcula el total sumando los detalles no eliminados."""
        return sum(
            detalle.precio_final()
            for detalle in self.detalles
            if not detalle.eliminado
        )

    def to_dict(self) -> dict:
        """Convierte el ticket a diccionario."""
        return {
            "id": self.id,
            "fecha": self.fecha,
            "supermercado": self.supermercado,
            "total_detectado": self.total_detectado,
            "total_confirmado": self.total_confirmado,
            "ruta_imagen": self.ruta_imagen,
            "texto_ocr": self.texto_ocr,
            "hash_imagen": self.hash_imagen,
            "created_at": self.created_at,
        }

    def resumen_telegram(self) -> str:
        """
        Genera un resumen formateado para enviar por Telegram.
        """
        lineas = [
            "🧾 Ticket detectado",
            f"📅 Fecha: {self.fecha}",
            f"🏪 Supermercado: {self.supermercado}",
            "",
        ]

        for i, detalle in enumerate(self.detalles, start=1):
            if not detalle.eliminado:
                precio = detalle.precio_final()
                lineas.append(
                    f"{i}. {detalle.descripcion_original} — {detalle.categoria.capitalize()} — {precio:.2f}€"
                )

        lineas.extend([
            "",
            f"💰 Total detectado: {self.total_final():.2f}€",
            "",
            "Comandos:",
            "• confirmar",
            "• precio <n> <nuevo_precio>",
            "• categoria <n> <nueva_categoria>",
            "• eliminar <n>",
            "• fecha <YYYY-MM-DD>",
            "• cancelar",
        ])

        return "\n".join(lineas)
