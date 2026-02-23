# Instrucciones de Uso — GastoTrack

## 📋 Índice

1. [Instalación](#instalación)
2. [Configuración](#configuración)
3. [Uso del Bot](#uso-del-bot)
4. [Uso del Dashboard](#uso-del-dashboard)
5. [Solución de Problemas](#solución-de-problemas)

---

## Instalación

### 1. Requisitos previos

- **Python 3.12** instalado
- **Poetry** instalado
- **Tesseract OCR** instalado

#### Instalar Tesseract en Ubuntu/Debian

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-spa
```

#### Verificar instalación de Tesseract

```bash
tesseract --version
```

Deberías ver algo como:

```
tesseract 5.x.x
```

### 2. Clonar el repositorio

```bash
cd ~/git/personal
git clone <url-del-repositorio> project-gastotrack
cd project-gastotrack
```

### 3. Configurar Poetry

```bash
poetry config virtualenvs.in-project true
```

### 4. Instalar dependencias

```bash
poetry install
```

Esto creará un entorno virtual en `.venv/` e instalará todas las dependencias.

---

## Configuración

### 1. Crear archivo `.env`

```bash
cp .env.example .env
```

### 2. Obtener token del bot de Telegram

1. Abrir Telegram y buscar [@BotFather](https://t.me/BotFather)
2. Enviar `/newbot`
3. Seguir las instrucciones para crear tu bot
4. Copiar el token que te proporciona

### 3. Editar `.env`

Abrir `.env` con tu editor favorito:

```bash
nano .env
```

Configurar las variables:

```env
TELEGRAM_TOKEN=tu_token_aqui
OCR_LANGUAGE=spa
DB_PATH=datos/gastotrack.db
IMAGES_DIR=tickets_images
CATEGORIES_FILE=datos/categorias.json
```

**Importante:** Reemplaza `tu_token_aqui` con el token real de tu bot.

### 4. Verificar configuración

```bash
poetry run python -c "from gastotrack.config import Config; Config.validar(); print(Config.mostrar_config())"
```

Si todo está bien, verás la configuración sin errores.

---

## Uso del Bot

### 1. Iniciar el bot

```bash
poetry run python -m gastotrack.bot
```

Deberías ver:

```
Bot iniciado. Presiona Ctrl+C para detener.
```

### 2. Interactuar con el bot

1. Abrir Telegram
2. Buscar tu bot por el nombre que le diste
3. Enviar `/start`

### 3. Enviar un ticket

1. Tomar foto del ticket con tu móvil
2. Enviar la foto al bot
3. Esperar a que procese (10-30 segundos)
4. Revisar el resumen

### 4. Corregir datos

Si el bot detectó algo mal, puedes corregirlo:

#### Cambiar precio de una línea

```
precio 1 8.50
```

Esto cambia el precio de la línea 1 a 8.50€.

#### Cambiar categoría

```
categoria 2 bebidas
```

Esto cambia la categoría de la línea 2 a "bebidas" y el bot aprende para futuras clasificaciones.

#### Eliminar una línea

```
eliminar 3
```

Esto marca la línea 3 como eliminada (no se borra físicamente).

#### Cambiar fecha

```
fecha 2026-02-17
```

Esto cambia la fecha del ticket.

### 5. Confirmar y guardar

Cuando todo esté correcto:

```
confirmar
```

El ticket se guarda en la base de datos.

### 6. Cancelar

Si quieres descartar el ticket:

```
cancelar
```

O usar el comando:

```
/cancelar
```

### 7. Ver estadísticas rápidas

```
/stats
```

---

## Uso del Dashboard

### 1. Iniciar el dashboard

En una **nueva terminal** (mantén el bot ejecutándose en la otra):

```bash
cd ~/git/personal/project-gastotrack
poetry run streamlit run src/gastotrack/dashboard.py
```

### 2. Abrir en el navegador

El dashboard se abrirá automáticamente en tu navegador en:

```
http://localhost:8501
```

Si no se abre automáticamente, copia y pega esa URL en tu navegador.

### 3. Navegar por las vistas

En la barra lateral izquierda, selecciona:

- **📊 Resumen General**: Métricas principales y comparativa mensual
- **📈 Evolución Temporal**: Gráfico de evolución con filtro por categoría
- **🏷️ Distribución**: Gráficos de distribución por categoría y supermercado

---

## Solución de Problemas

### El bot no responde

1. Verificar que el bot está ejecutándose
2. Verificar que el token en `.env` es correcto
3. Verificar conexión a internet

### Error "Tesseract not found"

Instalar Tesseract:

```bash
sudo apt install tesseract-ocr tesseract-ocr-spa
```

### Error "TELEGRAM_TOKEN no está configurado"

Editar `.env` y añadir el token:

```bash
nano .env
```

### El OCR no detecta bien el texto

- Asegurarse de que la foto es clara y bien iluminada
- Evitar sombras y reflejos
- Tomar la foto desde arriba, perpendicular al ticket
- Si el ticket es muy largo, tomar varias fotos

### El bot clasifica mal los productos

Corregir la categoría con:

```
categoria <número> <categoría_correcta>
```

El bot aprenderá y mejorará con el tiempo.

### Error al guardar ticket duplicado

El bot detecta duplicados por:
- Hash de la imagen (misma foto)
- Fecha + total + supermercado (mismo ticket, foto diferente)

Si quieres guardarlo de todos modos, el bot te pedirá confirmación.

### El dashboard no muestra datos

1. Verificar que hay tickets guardados (usar `/stats` en el bot)
2. Verificar que la ruta de la base de datos en `.env` es correcta
3. Reiniciar el dashboard

### Ejecutar tests

Para verificar que todo funciona correctamente:

```bash
poetry run pytest
```

Deberías ver todos los tests pasando (verde).

---

## Comandos Útiles

### Ver logs del bot

El bot imprime logs en la terminal. Para guardarlos en un archivo:

```bash
poetry run python -m gastotrack.bot 2>&1 | tee bot.log
```

### Hacer backup de la base de datos

```bash
cp datos/gastotrack.db datos/gastotrack_backup_$(date +%Y%m%d).db
```

### Ver contenido de la base de datos

```bash
sqlite3 datos/gastotrack.db
```

Dentro de sqlite3:

```sql
.tables
SELECT * FROM ticket LIMIT 5;
.quit
```

### Actualizar dependencias

```bash
poetry update
```

---

## Consejos de Uso

1. **Tomar fotos claras**: La calidad del OCR depende de la calidad de la foto
2. **Revisar siempre**: Dedica 10-15 segundos a revisar los datos antes de confirmar
3. **Corregir categorías**: Cuando corriges una categoría, el bot aprende
4. **Backup regular**: Haz backup de `datos/gastotrack.db` regularmente
5. **Mantener el bot ejecutándose**: Puedes usar `screen` o `tmux` para mantener el bot en segundo plano

### Usar screen para mantener el bot ejecutándose

```bash
# Instalar screen si no lo tienes
sudo apt install screen

# Crear sesión
screen -S gastotrack-bot

# Dentro de screen, ejecutar el bot
cd ~/git/personal/project-gastotrack
poetry run python -m gastotrack.bot

# Desconectar (Ctrl+A, luego D)

# Reconectar más tarde
screen -r gastotrack-bot
```

---

## Soporte

Si encuentras algún problema no documentado aquí, revisa:

1. Los logs del bot en la terminal
2. El archivo `README.md`
3. El plan detallado en `plans/plan.md`
