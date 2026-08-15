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

Mi Recetario incluye un **importador de Facebook** integrado: captura los
vídeos de tus *colecciones guardadas* y los descarga con un clic, sin
necesidad de herramientas externas.

### 📥 El flujo recomendado: la pestaña «Facebook»

1. Abre Mi Recetario y pulsa **Facebook → Abrir Facebook**. Se abre una
   **ventana nueva** con Facebook y Mi Recetario se queda abierto en la suya.
2. Inicia sesión en Facebook como siempre, con tu verificación en dos pasos si
   la tienes. **Solo la primera vez**: la sesión se recuerda entre ejecuciones
   (la app guarda las cookies en `data/webview/`).
3. Entra a una colección de tus guardados. Abajo a la derecha verás un panel
   con tres botones:
   - **«⬇️ Descargar toda la colección»** — recorre toda la colección
     automáticamente (Facebook va cargando más vídeos al llegar abajo),
     recopila todos los vídeos y arranca la descarga con `yt-dlp`.
   - **«📥 Enviar vídeos visibles»** — envía solo los vídeos que se ven en
     pantalla.
   - **«↩ Cerrar Facebook»** — cierra la ventana de Facebook; Mi Recetario
     sigue abierto.
4. Verás un aviso verde al empezar la descarga. Su **progreso se ve en vivo**
   en la ventana de Mi Recetario: la pestaña **Facebook** muestra la lista por
   vídeo con su barra de porcentaje, y mientras se descarga aparece también un
   **indicador inferior** visible desde cualquier pestaña (pulsarlo te lleva a
   la lista). Al terminar, los vídeos quedan en tu carpeta y aparecen en la
   **Biblioteca**.

Para que la descarga funcione, instala `yt-dlp` (solo hace falta una vez):

```bash
sudo apt install yt-dlp
```

> 🔑 **Colecciones privadas**: tus listas guardadas son privadas, pero el botón
> las lee igualmente porque corre dentro de tu sesión iniciada. Para
> **descargar** esos vídeos, al capturar la app exporta las cookies de tu
> sesión a `data/cookies/fb_cookies.txt` y se las pasa a `yt-dlp`, que así
> descarga con tu sesión (no con el navegador). Si caducan, vuelve a abrir
> Facebook desde la app y captura de nuevo: se refrescan solas.

> 🔒 **HTTPS local**: la app se sirve por HTTPS con un certificado autofirmado
> (se genera solo con `openssl` en `data/cert/`). Es necesario porque Facebook
> es HTTPS y WebKitGTK bloquea los envíos desde una página segura hacia
> `http://127.0.0.1` (contenido mixto). Todo sigue siendo local: el servidor
> solo escucha en 127.0.0.1.

> 📡 **Cómo se envían los vídeos a la app**: Facebook impone una política de
> seguridad (CSP) que prohíbe a cualquier página suya hacer *fetch* hacia
> `127.0.0.1`. Por eso el botón flotante **no usa HTTP**: envía los vídeos por
> el **canal nativo de WebKit** (el puente interno de pywebview), que llega
> directo a la app sin pasar por la red. Ni el CSP, ni CORS ni el contenido
> mixto pueden bloquearlo.

### 🖱️ Alternativa manual (sin usar la pestaña Facebook)

Si prefieres el método 100 % manual, también puedes:

1. En Facebook, abre el vídeo y pulsa **clic derecho → «Guardar vídeo como…»**
   (o usa un descargador individual como `yt-dlp` pegando la URL).
2. Deja los archivos en la carpeta de vídeos de la app (por defecto
   `~/Videos/Recetas`).
3. Abre Mi Recetario, pulsa **Escanear** y el vídeo aparece en la Biblioteca.

En ese caso, la pestaña Facebook te ofrece también un *bookmarklet* para
arrastrar a la barra de marcadores de tu navegador y capturar desde allí.

> ⚠️ El importador navega Facebook con tu cuenta (igual que harías tú a mano)
> y solo recoge los vídeos que **tú** ves en pantalla; no rastrea tu perfil ni
> el de nadie. Como con cualquier automatización, conviene usarlo con
> moderación para no llamar la atención sobre tu cuenta.

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
- **Facebook**: se abre en una **ventana propia** (Mi Recetario sigue abierto),
  captura tus vídeos guardados con tu propia sesión y los descarga con
  `yt-dlp` a tu carpeta, con el **progreso en vivo** desde cualquier pestaña.

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
| Los vídeos privados de Facebook no se descargan (error de autenticación) | Las cookies caducaron. Abre Facebook desde la app y captura de nuevo: la app las refresca automáticamente |
| No veo el progreso de la descarga | Mientras se descarga, hay un indicador inferior en cualquier pestaña; la lista completa por vídeo está en la pestaña Facebook |

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
