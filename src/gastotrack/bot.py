"""
Bot de Telegram para GastoTrack.
Gestiona la interacción con el usuario para procesar tickets.
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from gastotrack.config import Config
from gastotrack.ocr import extraer_texto, OCRError
from gastotrack.parser import parsear_ticket, ParserError, ParserConfigError
from gastotrack.clasificador import Clasificador
from gastotrack.bd import BaseDatos
from gastotrack.modelos import Ticket, DetalleTicket

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Diccionario para almacenar sesiones activas (chat_id -> datos del ticket)
sesiones_activas: dict[int, dict] = {}


def calcular_hash_imagen(ruta_imagen: str) -> str:
    """
    Calcula el hash SHA-256 de una imagen.

    Args:
        ruta_imagen: Ruta a la imagen

    Returns:
        Hash SHA-256 en formato hexadecimal
    """
    with open(ruta_imagen, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /start."""
    mensaje_bienvenida = """
¡Bienvenido a GastoTrack! 🧾

Envíame una foto de tu ticket de compra y te ayudaré a registrarlo.

Comandos disponibles:
/start - Mostrar este mensaje
/ayuda - Mostrar ayuda
/cancelar - Cancelar ticket actual
/stats - Ver estadísticas rápidas
"""
    await update.message.reply_text(mensaje_bienvenida)


async def comando_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /ayuda."""
    mensaje_ayuda = """
📖 Ayuda de GastoTrack

1️⃣ Envía una foto de tu ticket
2️⃣ Revisa los datos detectados
3️⃣ Corrige si es necesario con:
   • precio <n> <nuevo_precio>
   • categoria <n> <nueva_categoria>
   • eliminar <n>
   • fecha <YYYY-MM-DD>
4️⃣ Confirma con: confirmar

Comandos:
/start - Inicio
/ayuda - Esta ayuda
/cancelar - Cancelar ticket actual
/stats - Estadísticas
"""
    await update.message.reply_text(mensaje_ayuda)


async def comando_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /cancelar."""
    chat_id = update.effective_chat.id

    if chat_id in sesiones_activas:
        del sesiones_activas[chat_id]
        await update.message.reply_text("✅ Ticket cancelado.")
    else:
        await update.message.reply_text("No hay ningún ticket en proceso.")


async def comando_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /stats."""
    try:
        with BaseDatos() as bd:
            stats = bd.obtener_estadisticas_basicas()

        mensaje = f"""
📊 Estadísticas

💰 Total gastado: {stats['total_gastado']:.2f}€
🧾 Número de tickets: {stats['num_tickets']}

🏪 Top supermercados:
"""
        for super_nombre, total in list(stats['gasto_por_supermercado'].items())[:3]:
            mensaje += f"  • {super_nombre}: {total:.2f}€\n"

        mensaje += "\n🏷️ Top categorías:\n"
        for cat, total in list(stats['gasto_por_categoria'].items())[:5]:
            mensaje += f"  • {cat.capitalize()}: {total:.2f}€\n"

        await update.message.reply_text(mensaje)

    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}")
        await update.message.reply_text("❌ Error al obtener estadísticas.")


async def procesar_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para procesar imágenes de tickets."""
    chat_id = update.effective_chat.id

    # Informar que se está procesando
    mensaje_procesando = await update.message.reply_text("⏳ Procesando ticket...")

    try:
        # Descargar imagen
        foto = update.message.photo[-1]  # Obtener la foto de mayor resolución
        archivo = await foto.get_file()

        # Guardar imagen con timestamp y hash corto
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f"ticket_{timestamp}.jpg"
        ruta_imagen = Path(Config.IMAGES_DIR) / nombre_archivo

        await archivo.download_to_drive(ruta_imagen)

        # Calcular hash de la imagen
        hash_imagen = calcular_hash_imagen(str(ruta_imagen))

        # Verificar duplicados
        with BaseDatos() as bd:
            if bd.existe_ticket_por_hash(hash_imagen):
                await mensaje_procesando.edit_text(
                    "⚠️ Esta imagen ya fue procesada anteriormente.\n"
                    "¿Quieres procesarla de nuevo? Responde 'si' para continuar."
                )
                # TODO: Implementar confirmación de duplicado
                return

        # Extraer texto con OCR
        texto_ocr = extraer_texto(str(ruta_imagen))

        # Parsear ticket
        datos_parseados = parsear_ticket(texto_ocr)

        # Clasificar productos
        clasificador = Clasificador()
        detalles = []

        for producto in datos_parseados['productos']:
            categoria = clasificador.clasificar(producto.descripcion)
            detalle = DetalleTicket(
                descripcion_original=producto.descripcion,
                descripcion_normalizada=clasificador.normalizar_texto(producto.descripcion),
                categoria=categoria,
                precio_detectado=producto.precio,
            )
            detalles.append(detalle)

        # Crear objeto Ticket
        ticket = Ticket(
            fecha=datos_parseados['fecha'],
            supermercado=datos_parseados['supermercado'],
            total_detectado=datos_parseados['total'],
            ruta_imagen=str(ruta_imagen),
            texto_ocr=texto_ocr,
            hash_imagen=hash_imagen,
            detalles=detalles,
        )

        # Guardar en sesión activa
        sesiones_activas[chat_id] = {
            'ticket': ticket,
            'clasificador': clasificador,
        }

        # Enviar resumen
        await mensaje_procesando.edit_text(ticket.resumen_telegram())

    except OCRError as e:
        logger.error(f"Error de OCR: {e}")
        await mensaje_procesando.edit_text(f"❌ Error al procesar la imagen: {e}")
    except ParserConfigError as e:
        logger.error(f"Error de configuración del parser: {e}")
        await mensaje_procesando.edit_text(
            "⚠️ Error de configuración del sistema.\n"
            "Por favor, contacta al administrador."
        )
    except ParserError as e:
        logger.error(f"Error de parseo: {e}")
        await mensaje_procesando.edit_text(
            "❌ No pude procesar este ticket.\n"
            "Por favor, intenta con una foto más clara o envía los datos manualmente."
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        await mensaje_procesando.edit_text(
            "❌ Error inesperado al procesar el ticket. "
            "Por favor, intenta de nuevo o contacta al administrador."
        )


async def procesar_comando_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para procesar comandos de texto (confirmar, precio, categoria, etc.)."""
    chat_id = update.effective_chat.id
    texto = update.message.text.strip().lower()

    # Verificar que hay una sesión activa
    if chat_id not in sesiones_activas:
        await update.message.reply_text(
            "No hay ningún ticket en proceso. Envía una foto para empezar."
        )
        return

    sesion = sesiones_activas[chat_id]
    ticket = sesion['ticket']
    clasificador = sesion['clasificador']

    # Comando: confirmar
    if texto == 'confirmar':
        try:
            with BaseDatos() as bd:
                # Verificar duplicado por datos
                if bd.existe_ticket_por_datos(
                    ticket.fecha,
                    ticket.total_final(),
                    ticket.supermercado
                ):
                    await update.message.reply_text(
                        "⚠️ Ya existe un ticket con la misma fecha, total y supermercado.\n"
                        "Si quieres guardarlo de todos modos, responde 'forzar'."
                    )
                    return

                # Guardar ticket
                ticket_id = bd.insertar_ticket(ticket)

            # Limpiar sesión
            del sesiones_activas[chat_id]

            await update.message.reply_text(
                f"✅ Ticket guardado correctamente (ID: {ticket_id})\n"
                f"Total: {ticket.total_final():.2f}€"
            )

        except Exception as e:
            logger.error(f"Error al guardar ticket: {e}", exc_info=True)
            await update.message.reply_text("❌ Error al guardar el ticket.")

    # Comando: cancelar
    elif texto == 'cancelar':
        del sesiones_activas[chat_id]
        await update.message.reply_text("✅ Ticket cancelado.")

    # Comando: precio <n> <nuevo_precio>
    elif texto.startswith('precio '):
        match = re.match(r'precio\s+(\d+)\s+([\d.,]+)', texto)
        if not match:
            await update.message.reply_text(
                "❌ Formato incorrecto. Usa: precio <número> <nuevo_precio>\n"
                "Ejemplo: precio 1 8.50"
            )
            return

        indice = int(match.group(1)) - 1
        nuevo_precio_str = match.group(2).replace(',', '.')

        try:
            nuevo_precio = float(nuevo_precio_str)
        except ValueError:
            await update.message.reply_text("❌ Precio inválido.")
            return

        if indice < 0 or indice >= len(ticket.detalles):
            await update.message.reply_text("❌ Número de línea inválido.")
            return

        ticket.detalles[indice].precio_confirmado = nuevo_precio
        ticket.total_confirmado = ticket.calcular_total_detalles()

        await update.message.reply_text(
            f"✅ Precio actualizado.\n\n{ticket.resumen_telegram()}"
        )

    # Comando: categoria <n> <nueva_categoria>
    elif texto.startswith('categoria '):
        match = re.match(r'categoria\s+(\d+)\s+(.+)', texto)
        if not match:
            await update.message.reply_text(
                "❌ Formato incorrecto. Usa: categoria <número> <nueva_categoria>\n"
                "Ejemplo: categoria 1 bebidas"
            )
            return

        indice = int(match.group(1)) - 1
        nueva_categoria = match.group(2).strip()

        if indice < 0 or indice >= len(ticket.detalles):
            await update.message.reply_text("❌ Número de línea inválido.")
            return

        detalle = ticket.detalles[indice]
        detalle.categoria = nueva_categoria

        # Aprender nueva categoría
        clasificador.aprender_categoria(detalle.descripcion_original, nueva_categoria)

        await update.message.reply_text(
            f"✅ Categoría actualizada y aprendida.\n\n{ticket.resumen_telegram()}"
        )

    # Comando: eliminar <n>
    elif texto.startswith('eliminar '):
        match = re.match(r'eliminar\s+(\d+)', texto)
        if not match:
            await update.message.reply_text(
                "❌ Formato incorrecto. Usa: eliminar <número>\n"
                "Ejemplo: eliminar 1"
            )
            return

        indice = int(match.group(1)) - 1

        if indice < 0 or indice >= len(ticket.detalles):
            await update.message.reply_text("❌ Número de línea inválido.")
            return

        ticket.detalles[indice].eliminado = True
        ticket.total_confirmado = ticket.calcular_total_detalles()

        await update.message.reply_text(
            f"✅ Línea eliminada.\n\n{ticket.resumen_telegram()}"
        )

    # Comando: fecha <YYYY-MM-DD>
    elif texto.startswith('fecha '):
        match = re.match(r'fecha\s+(\d{4}-\d{2}-\d{2})', texto)
        if not match:
            await update.message.reply_text(
                "❌ Formato incorrecto. Usa: fecha YYYY-MM-DD\n"
                "Ejemplo: fecha 2026-02-18"
            )
            return

        nueva_fecha = match.group(1)

        # Validar fecha
        try:
            datetime.strptime(nueva_fecha, '%Y-%m-%d')
        except ValueError:
            await update.message.reply_text("❌ Fecha inválida.")
            return

        ticket.fecha = nueva_fecha

        await update.message.reply_text(
            f"✅ Fecha actualizada.\n\n{ticket.resumen_telegram()}"
        )

    else:
        await update.message.reply_text(
            "❌ Comando no reconocido. Usa /ayuda para ver los comandos disponibles."
        )


def main() -> None:
    """Función principal para ejecutar el bot."""
    # Validar configuración
    try:
        Config.validar()
        print(Config.mostrar_config())
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return

    # Crear directorios necesarios
    Path(Config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)

    # Crear aplicación
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    # Registrar handlers
    application.add_handler(CommandHandler("start", comando_start))
    application.add_handler(CommandHandler("ayuda", comando_ayuda))
    application.add_handler(CommandHandler("cancelar", comando_cancelar))
    application.add_handler(CommandHandler("stats", comando_stats))
    application.add_handler(MessageHandler(filters.PHOTO, procesar_imagen))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_comando_texto))

    # Iniciar bot
    logger.info("Bot iniciado. Presiona Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
