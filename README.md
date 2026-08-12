# 🍲 Mi Recetario — recetas de cocina en vídeo

Gestor de escritorio para tu colección de **vídeos de recetas de Facebook**:

1. **Organiza** los vídeos que tienes guardados en una carpeta de tu equipo.
2. **Transcríbelos a texto** de forma local con Whisper (español incluido) — tus
   vídeos nunca salen de tu ordenador.
3. **Edítalos como recetas**: ingredientes, pasos, categorías, etiquetas,
   búsqueda y exportación a Markdown.

## Cómo conseguir los vídeos de Facebook

Facebook no permite que terceros accedan a tus *colecciones guardadas* de forma
automática (ni su API ni `yt-dlp` pueden leerlas), así que el flujo recomendado y
seguro es:

1. En Facebook, abre el vídeo de tu colección y pulsa **clic derecho → «Guardar
   vídeo como…»** (o usa un descargador individual como `yt-dlp` pegando la URL).
2. Deja los archivos en la carpeta de vídeos de la app (por defecto
   `~/Videos/Recetas`).
3. Pulsa **Escanear** y el vídeo aparece en la Biblioteca. Desde ahí, **Transcribir**.

> ⚠️ Automatizar la descarga de la colección (scraping) viola los Términos de
> Servicio de Facebook y puede bloquear tu cuenta. Este programa se limita a
> gestionar los vídeos que tú ya has descargado.

## Instalación

Requiere **Python 3.10+** y `venv`.

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Uso

```bash
# Ventana nativa de escritorio (recomendado)
venv/bin/python run.py

# En el navegador
venv/bin/python run.py --web

# Solo servidor HTTP (para pruebas / API)
venv/bin/python run.py --serve --port 8765
```

El primer uso de la transcripción descarga el modelo de Whisper elegido
(por defecto `small`). Cambia el modelo en **Ajustes** según tu CPU.

## Funciones

- **Biblioteca**: tarjetas con miniatura, búsqueda por título/texto,
  filtros por categoría y estado.
- **Editor de receta**: reproductor de vídeo, transcripción editable en vivo,
  listas de ingredientes y pasos, etiquetas, notas y exportación `.md`.
- **Cola de transcripción**: progreso en tiempo real, cancelación y reintento.
- **Ajustes**: carpeta de vídeos, modelo de Whisper, idioma, hilos de CPU y VAD.
- **Importar**: arrastra vídeos a la ventana para copiarlos a tu carpeta.

## Estructura

```
app/            Backend (Flask, SQLite, Whisper, escáner de vídeos)
web/            Interfaz (HTML/CSS/JS, sin frameworks externos)
data/           Base de datos, miniaturas y ajustes (se crea al primer uso)
run.py          Punto de entrada
```

Todo es **local y privado**: base de datos SQLite, transcripción en tu CPU.
