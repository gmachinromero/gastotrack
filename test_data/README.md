# Test Data - Imágenes de Prueba

Este directorio está destinado a almacenar imágenes de tickets para pruebas manuales.

## Cómo usar

1. **Coloca una foto de un ticket** en este directorio. Por ejemplo:
   - `ticket_mercadona.jpg`
   - `ticket_carrefour.jpg`
   - etc.

2. **Ejecuta el script de prueba manual**:

   ```bash
   poetry run python test_manual.py test_data/ticket_mercadona.jpg
   ```

3. **El script mostrará**:
   - ✅ Texto extraído por OCR
   - ✅ Productos detectados con precios
   - ✅ Clasificación automática por categoría
   - ✅ Resumen completo del ticket

## Ejemplo de salida

```
🧾 GastoTrack - Prueba Manual

📸 Imagen: test_data/ticket_mercadona.jpg

============================================================
  1. PRUEBA DE OCR
============================================================

✅ Tesseract encontrado
📄 Procesando imagen: test_data/ticket_mercadona.jpg
✅ Texto extraído (523 caracteres)

--- TEXTO OCR ---
MERCADONA
C/ EJEMPLO 123
18/02/2026

POLLO PECHUGA 8,90€
LECHE ENTERA 2,10€
PAN BARRA 1,50€

TOTAL: 12,50€
--- FIN TEXTO OCR ---

============================================================
  2. PRUEBA DE PARSER
============================================================

📅 Fecha detectada: 2026-02-18
🏪 Supermercado: MERCADONA
💰 Total detectado: 12.50€
📦 Productos encontrados: 3

--- PRODUCTOS ---
1. POLLO PECHUGA                          8.90€
2. LECHE ENTERA                           2.10€
3. PAN BARRA                              1.50€
--- FIN PRODUCTOS ---

============================================================
  3. PRUEBA DE CLASIFICADOR
============================================================

✅ Clasificador cargado
📚 Categorías disponibles: carne, pescado, lacteos, panaderia, bebidas, verduras, frutas, hogar

--- CLASIFICACIÓN ---
1. POLLO PECHUGA                          → carne           (8.90€)
2. LECHE ENTERA                           → lacteos         (2.10€)
3. PAN BARRA                              → panaderia       (1.50€)
--- FIN CLASIFICACIÓN ---

============================================================
  4. TICKET COMPLETO
============================================================

🧾 Ticket detectado
📅 Fecha: 2026-02-18
🏪 Supermercado: MERCADONA

1. POLLO PECHUGA — Carne — 8.90€
2. LECHE ENTERA — Lacteos — 2.10€
3. PAN BARRA — Panaderia — 1.50€

💰 Total detectado: 12.50€

Comandos:
• confirmar
• precio <n> <nuevo_precio>
• categoria <n> <nueva_categoria>
• eliminar <n>
• fecha <YYYY-MM-DD>
• cancelar

============================================================
  RESUMEN FINAL
============================================================

✅ Procesamiento completado
   - Productos detectados: 3
   - Productos clasificados: 3
   - Total: 12.50€
   - Supermercado: MERCADONA
   - Fecha: 2026-02-18

📊 Distribución por categoría:
   - Carne: 1 producto(s)
   - Lacteos: 1 producto(s)
   - Panaderia: 1 producto(s)

✅ Prueba completada
```

## Consejos para mejores resultados

1. **Calidad de la imagen**:
   - Foto clara y bien iluminada
   - Sin sombras ni reflejos
   - Perpendicular al ticket (desde arriba)
   - Resolución suficiente (mínimo 1000px de ancho)

2. **Formato del ticket**:
   - Tickets impresos funcionan mejor que manuscritos
   - Texto negro sobre fondo blanco
   - Sin arrugas ni dobleces

3. **Tipos de archivo soportados**:
   - JPG/JPEG
   - PNG
   - WEBP

## Notas

- Este directorio está incluido en `.gitignore`, por lo que las imágenes no se subirán al repositorio
- Puedes usar este script tantas veces como quieras para probar diferentes tickets
- Si el OCR no detecta bien algo, puedes ajustar los patrones en `src/gastotrack/parser.py`
