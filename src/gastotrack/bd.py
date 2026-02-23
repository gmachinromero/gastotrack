"""
Módulo de base de datos para GastoTrack.
Gestiona la persistencia de tickets y detalles en SQLite.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime

from gastotrack.modelos import Ticket, DetalleTicket
from gastotrack.config import Config


class BaseDatos:
    """Gestiona la conexión y operaciones con la base de datos SQLite."""

    def __init__(self, ruta_bd: Optional[str] = None):
        """
        Inicializa la conexión a la base de datos.

        Args:
            ruta_bd: Ruta al archivo de base de datos. Si es None, usa Config.DB_PATH
        """
        self.ruta_bd = ruta_bd or Config.DB_PATH
        Path(self.ruta_bd).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.ruta_bd)
        self.conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
        self._crear_tablas()

    def _crear_tablas(self) -> None:
        """Crea las tablas si no existen."""
        cursor = self.conn.cursor()

        # Tabla de tickets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                supermercado TEXT NOT NULL,
                total_detectado REAL NOT NULL,
                total_confirmado REAL NOT NULL,
                ruta_imagen TEXT NOT NULL,
                texto_ocr TEXT NOT NULL,
                hash_imagen TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(hash_imagen)
            )
        """)

        # Tabla de detalles de ticket
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detalle_ticket (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                descripcion_original TEXT NOT NULL,
                descripcion_normalizada TEXT NOT NULL,
                categoria TEXT NOT NULL,
                precio_detectado REAL NOT NULL,
                precio_confirmado REAL NOT NULL,
                eliminado INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id)
            )
        """)

        # Índices para mejorar consultas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticket_fecha 
            ON ticket(fecha)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticket_hash 
            ON ticket(hash_imagen)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_detalle_ticket_id 
            ON detalle_ticket(ticket_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_detalle_categoria 
            ON detalle_ticket(categoria)
        """)

        self.conn.commit()

    def insertar_ticket(self, ticket: Ticket) -> int:
        """
        Inserta un ticket con sus detalles en la base de datos.

        Args:
            ticket: Objeto Ticket a insertar

        Returns:
            ID del ticket insertado

        Raises:
            sqlite3.IntegrityError: Si el hash de la imagen ya existe
        """
        cursor = self.conn.cursor()

        # Insertar ticket
        cursor.execute("""
            INSERT INTO ticket (
                fecha, supermercado, total_detectado, total_confirmado,
                ruta_imagen, texto_ocr, hash_imagen, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket.fecha,
            ticket.supermercado,
            ticket.total_detectado,
            ticket.total_confirmado,
            ticket.ruta_imagen,
            ticket.texto_ocr,
            ticket.hash_imagen,
            ticket.created_at or datetime.now().isoformat(),
        ))

        ticket_id = cursor.lastrowid

        # Insertar detalles
        for detalle in ticket.detalles:
            cursor.execute("""
                INSERT INTO detalle_ticket (
                    ticket_id, descripcion_original, descripcion_normalizada,
                    categoria, precio_detectado, precio_confirmado, eliminado
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_id,
                detalle.descripcion_original,
                detalle.descripcion_normalizada,
                detalle.categoria,
                detalle.precio_detectado,
                detalle.precio_confirmado,
                1 if detalle.eliminado else 0,
            ))

        self.conn.commit()
        return ticket_id

    def existe_ticket_por_hash(self, hash_imagen: str) -> bool:
        """
        Verifica si existe un ticket con el hash de imagen dado.

        Args:
            hash_imagen: Hash SHA-256 de la imagen

        Returns:
            True si existe, False en caso contrario
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ticket WHERE hash_imagen = ?", (hash_imagen,))
        count = cursor.fetchone()[0]
        return count > 0

    def existe_ticket_por_datos(self, fecha: str, total: float, supermercado: str) -> bool:
        """
        Verifica si existe un ticket con la misma fecha, total y supermercado.

        Args:
            fecha: Fecha del ticket (YYYY-MM-DD)
            total: Total del ticket
            supermercado: Nombre del supermercado

        Returns:
            True si existe, False en caso contrario
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM ticket 
            WHERE fecha = ? AND ABS(total_confirmado - ?) < 0.01 AND supermercado = ?
        """, (fecha, total, supermercado))
        count = cursor.fetchone()[0]
        return count > 0

    def obtener_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """
        Obtiene un ticket por su ID, incluyendo sus detalles.

        Args:
            ticket_id: ID del ticket

        Returns:
            Objeto Ticket o None si no existe
        """
        cursor = self.conn.cursor()

        # Obtener ticket
        cursor.execute("SELECT * FROM ticket WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Obtener detalles
        cursor.execute("SELECT * FROM detalle_ticket WHERE ticket_id = ?", (ticket_id,))
        detalles_rows = cursor.fetchall()

        detalles = [
            DetalleTicket(
                id=d["id"],
                ticket_id=d["ticket_id"],
                descripcion_original=d["descripcion_original"],
                descripcion_normalizada=d["descripcion_normalizada"],
                categoria=d["categoria"],
                precio_detectado=d["precio_detectado"],
                precio_confirmado=d["precio_confirmado"],
                eliminado=bool(d["eliminado"]),
            )
            for d in detalles_rows
        ]

        return Ticket(
            id=row["id"],
            fecha=row["fecha"],
            supermercado=row["supermercado"],
            total_detectado=row["total_detectado"],
            total_confirmado=row["total_confirmado"],
            ruta_imagen=row["ruta_imagen"],
            texto_ocr=row["texto_ocr"],
            hash_imagen=row["hash_imagen"],
            created_at=row["created_at"],
            detalles=detalles,
        )

    def obtener_todos_tickets(self, limite: Optional[int] = None) -> list[Ticket]:
        """
        Obtiene todos los tickets, ordenados por fecha descendente.

        Args:
            limite: Número máximo de tickets a devolver (None = todos)

        Returns:
            Lista de objetos Ticket
        """
        cursor = self.conn.cursor()

        query = "SELECT id FROM ticket ORDER BY fecha DESC, created_at DESC"
        if limite:
            query += f" LIMIT {limite}"

        cursor.execute(query)
        ids = [row[0] for row in cursor.fetchall()]

        return [self.obtener_ticket(tid) for tid in ids if self.obtener_ticket(tid)]

    def obtener_estadisticas_basicas(self) -> dict:
        """
        Obtiene estadísticas básicas de los tickets.

        Returns:
            Diccionario con estadísticas
        """
        cursor = self.conn.cursor()

        # Total gastado
        cursor.execute("SELECT SUM(total_confirmado) FROM ticket")
        total_gastado = cursor.fetchone()[0] or 0.0

        # Número de tickets
        cursor.execute("SELECT COUNT(*) FROM ticket")
        num_tickets = cursor.fetchone()[0]

        # Gasto por categoría
        cursor.execute("""
            SELECT categoria, SUM(precio_confirmado) as total
            FROM detalle_ticket
            WHERE eliminado = 0
            GROUP BY categoria
            ORDER BY total DESC
        """)
        gasto_por_categoria = {row[0]: row[1] for row in cursor.fetchall()}

        # Gasto por supermercado
        cursor.execute("""
            SELECT supermercado, SUM(total_confirmado) as total
            FROM ticket
            GROUP BY supermercado
            ORDER BY total DESC
        """)
        gasto_por_supermercado = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_gastado": total_gastado,
            "num_tickets": num_tickets,
            "gasto_por_categoria": gasto_por_categoria,
            "gasto_por_supermercado": gasto_por_supermercado,
        }

    def cerrar(self) -> None:
        """Cierra la conexión a la base de datos."""
        self.conn.close()

    def __enter__(self):
        """Soporte para context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra la conexión al salir del context manager."""
        self.cerrar()
