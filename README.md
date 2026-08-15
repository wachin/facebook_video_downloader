# 🍲 Mi Recetario — recetas de cocina en vídeo

Un programa de escritorio para tu colección de **vídeos de recetas de Facebook**:

1. **Organiza** los vídeos que has guardado en una carpeta de tu equipo.
2. **Transcríbelos a texto** de forma local con Whisper (español incluido) —
   tus vídeos **nunca salen de tu ordenador**.
3. **Edítalos como recetas**: ingredientes, pasos, categorías, etiquetas,
   búsqueda y exportación a Markdown.

> 🐣 **Este README está escrito para principiantes totales.** Si nunca has
> usado la terminal, `pip` o `venv`, no pasa nada: sigue los pasos en orden
> y todo funcionará. Las palabras raras están explicadas.

---

## 1. Cómo conseguir los vídeos de Facebook

Facebook no permite que ningún programa acceda a tus *colecciones guardadas*
automáticamente (ni su API ni `yt-dlp` pueden leerlas). El flujo recomendado y
seguro es:

1. En Facebook, abre el vídeo y pulsa **clic derecho → «Guardar vídeo como…»**.
   (También vale usar un descargador individual como `yt-dlp` pegando la URL.)
2. Deja los archivos en la carpeta de vídeos de la app (por defecto
   `~/Videos/Recetas`).
3. Abre Mi Recetario, pulsa **Escanear** y el vídeo aparece en la Biblioteca.

> ⚠️ Automatizar la descarga de toda la colección viola los Términos de
> Servicio de Facebook y puede bloquear tu cuenta. Este programa solo gestiona
> los vídeos que **tú** ya has descargado.

### 📥 Alternativa: pestaña «Facebook» (importador guiado)

Desde la pestaña **Facebook** de la app puedes capturar los vídeos de tu página
*guardados* y descargarlos con un clic, **sin que la app vea nunca tu
contraseña**: tú inicias sesión en Facebook como siempre (con tu verificación
en dos pasos) en la ventana de la app o en tu navegador, y un botón flotante
(«📥 Enviar vídeos a Mi Recetario») recopila los vídeos visibles y los envía a
la app. Después los seleccionas y la app los descarga con `yt-dlp` a tu carpeta
de vídeos.

> ⚠️ Usar este importador implica navegar Facebook con tu cuenta; se recomienda
> no marcar esta opción si prefieres el método 100 % manual. La captura solo
> recoge los vídeos que **tú** ves en pantalla; no rastrea tu perfil.

Para que la descarga funcione necesitas `yt-dlp` instalado:

```bash
sudo apt install yt-dlp
```

Si usas tu navegador normal en lugar de la ventana de la app, el paso 2 de la
pestaña te ofrece un *bookmarklet* para arrastrar a la barra de marcadores.

> 🔐 **La sesión se recuerda**: la app guarda las cookies de Facebook en
> `data/webview/` (carpeta del proyecto), así que no tendrás que volver a
> iniciar sesión cada vez que la abras. Inicia sesión una sola vez y la app la
> mantiene entre ejecuciones.

---

## 2. Qué necesitas antes de empezar

- **Python 3.10 o superior** (casi cualquier Linux moderno lo trae).
- Una **terminal** (la ventanita donde se escriben comandos).
- **Conexión a internet** la primera vez (para descargar el motor de
  transcripción y el modelo de idioma).

Para comprobar si tienes Python, abre una terminal y escribe:

```bash
python3 --version
```

Si ves algo como `Python 3.11.x` o superior, estás listo. Si te da error o te
dice que falta `venv`, mira la sección [9. Solución de problemas](#9-solución-de-problemas).

---

## 3. ¿Qué es eso de `venv` y `pip`? (explicado sin tecnicismos)

Piensa en un programa de Python como una receta de cocina: necesita varios
"ingredientes" (paquetes) para funcionar: Flask, Pillow, el motor de
transcripción, etc.

- **`pip`** es la herramienta que descarga e instala esos ingredientes.
- **`venv`** (entorno virtual) es una **caja aislada** dentro de tu proyecto
  donde se guardan esos ingredientes, sin tocar el resto del sistema.

¿Por qué hace falta esta caja? Porque casi todos los ingredientes de Mi
Recetario existen como paquetes de tu distribución de Linux... **excepto uno**:
el motor de transcripción (`faster-whisper`). Ese solo se consigue con `pip`,
y lo correcto es instalarlo dentro de su caja (`venv`), no en el sistema.
Así no rompes nada, y si algo falla, borras la caja y la creas de nuevo.

> La carpeta del entorno virtual se llama `venv/` y vive dentro de la carpeta
> del proyecto. Se puede borrar y recrear cuando quieras: los datos de tus
> recetas están en otra carpeta (`data/`) y no se pierden.

---

## 4. Instalación paso a paso

Abre una terminal y copia los comandos **uno a uno**, pulsando Enter después
de cada uno.

**Paso 1 — Ve a la carpeta del proyecto.** (Cambia la ruta por la tuya si
instalaste el proyecto en otro sitio.)

```bash
cd ~/Dev3/recipe_book_downloader
```

**Paso 2 — Crea el entorno virtual (la "caja").** Esto solo se hace **una
vez**, en la primera instalación.

```bash
python3 -m venv venv
```

No verás ningún mensaje si todo ha ido bien. Eso es normal.

**Paso 3 — Activa el entorno virtual.** Fíjate en el `(venv)` que aparece
al principio de la línea: es la señal de que estás dentro de la caja.

```bash
source venv/bin/activate
```

**Paso 4 — Instala los ingredientes.** Esto descarga e instala todo lo que
el programa necesita (puede tardar unos minutos la primera vez).

```bash
pip install -r requirements.txt
```

**Paso 5 — Arranca el programa.**

```bash
python run.py
```

Se abrirá la ventana de **Mi Recetario**. 🎉

---

## 5. Activar y desactivar el entorno virtual

El entorno virtual se **activa** cuando quieres usar `pip` o `python` dentro
de él, y se **desactiva** cuando terminas.

### 🔓 Activar

```bash
source venv/bin/activate
```

Verás `(venv)` al principio de la línea del terminal:

```
(venv) usuario@equipo:~/Dev3/recipe_book_downloader$
```

Mientras esté ese `(venv)`, los comandos `python` y `pip` usan el entorno
del proyecto. Cuando lo cierres (cerrando la ventana), se desactiva solo.

### 🔒 Desactivar

```bash
deactivate
```

El `(venv)` desaparece de la línea y vuelves al sistema normal. (Si no lo
has activado antes, no hay nada que desactivar.)

### 🤓 Truco: no hace falta activar para usar la app

Para **lanzar el programa** no necesitas activar nada. Este comando funciona
siempre, estés donde estés (dentro de la carpeta del proyecto):

```bash
venv/bin/python run.py
```

Es la misma app, sin pasos extra. Mucha gente lo usa directamente.

---

## 6. Cómo usar el programa

### Opción A — ventana nativa de escritorio (recomendada)

```bash
venv/bin/python run.py
```

![](images/01-recipe_book_downloader.png)

### Opción B — en el navegador

```bash
venv/bin/python run.py --web
```

### Opción C — solo el servidor interno (para pruebas / API)

```bash
venv/bin/python run.py --serve --port 8765
```

**Sobre la primera transcripción:** la primera vez que pulses *Transcribir*,
el programa descarga el modelo de idioma (unos 460 MB el modelo *small* por
defecto, que se guarda en `~/.cache/huggingface`). Solo ocurre una vez.
Si tu ordenador es modesto, puedes elegir el modelo *tiny* o *base* en
**Ajustes** para que sea más rápido (a cambio de algo de precisión).

---

## 7. Funciones

- **Biblioteca**: tarjetas con miniatura, búsqueda por título/texto y
  filtros por categoría y estado.
- **Editor de receta**: reproductor de vídeo, transcripción editable en vivo,
  listas de ingredientes y pasos, etiquetas, notas y exportación `.md`.
- **Cola de transcripción**: progreso en tiempo real, cancelación y reintento.
- **Ajustes**: carpeta de vídeos, modelo de Whisper, idioma, hilos de CPU y VAD.
- **Importar**: arrastra vídeos a la ventana para copiarlos a tu carpeta.
- **Facebook**: captura tus vídeos guardados con tu propia sesión (sin guardar
  contraseñas) y descárgalos con `yt-dlp` directamente a tu carpeta.

---

## 8. Cómo actualizar el programa

Cuando haya una versión nueva:

```bash
cd ~/Dev3/recipe_book_downloader
git pull
source venv/bin/activate
pip install -r requirements.txt
```

(El `git pull` descarga el código nuevo y el `pip install` actualiza los
ingredientes si hace falta.)

---

## 9. Solución de problemas

|  Problema | Solución |
|--- |---|
| `python3: command not found`  | Instala Python: `sudo apt install python3` |
| `ensurepip is not available` o falta `venv` | Instala el módulo: `sudo apt install python3-venv` y repite el Paso 2 |
| `error: externally-managed-environment` | Es normal en Debian/MX: significa que pip no debe tocar el sistema. **Activa el venv** (Paso 3) y repite el Paso 4 |
| El venv está "roto" o algo raro ocurre | Bórralo y créalo de nuevo: `rm -rf venv` y repite los pasos 2 a 4. Tus recetas no se pierden (están en `data/`) |
| La transcripción tarda mucho | Elige un modelo más pequeño en **Ajustes** (tiny o base) |
| La descarga del modelo falla a mitad | Vuelve a intentarlo: reanuda donde se quedó. Si falla siempre, revisa tu conexión o proxy |

---

## 10. Estructura del proyecto

```
app/            Backend (Flask, SQLite, Whisper, escáner de vídeos)
web/            Interfaz (HTML/CSS/JS, sin frameworks externos)
data/           Base de datos, miniaturas y ajustes (se crea al primer uso)
venv/           Entorno virtual (NO se toca a mano; se crea con el Paso 2)
run.py          Punto de entrada
```

Todo es **local y privado**: base de datos SQLite y transcripción en tu CPU,
sin enviar nada a internet (excepto la descarga inicial del modelo de idioma).
