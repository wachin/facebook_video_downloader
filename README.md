# 🍲 Facebook Collections Downloader — cooking recipe videos

A desktop program for your collection of **cooking recipe videos from Facebook**:

1. **Organize** the videos you've saved to a folder on your computer.
2. **Transcribe them to text** locally with Whisper (99 languages supported) —
   your videos **never leave your computer**.
3. **Edit them as recipes**: ingredients, steps, categories, tags,
   search and export to Markdown.

> 🐣 **This README is written for complete beginners.** If you've never used
> a terminal, `pip`, or `venv`, that's okay: follow the steps in order and
> everything will work. Unfamiliar terms are explained.

> 📖 **[README en Español (Versión en español)](README_ES.md)**

---

## 1. How to get videos from Facebook

Facebook Collections Downloader includes a built-in **Facebook importer**: it captures the
videos from your *saved collections* and downloads them with one click, with
no need for external tools.

### 📥 Recommended workflow: the "Facebook" tab

1. Open Facebook Collections Downloader and click **Facebook → Open Facebook**. A **new
   window** opens with Facebook, while Facebook Collections Downloader stays open in its own
   window.
2. Log in to Facebook as usual, with your two-factor verification if you have
   it. **Only the first time**: the session is remembered between launches
   (the app stores cookies in `data/webview/`).
3. Go to one of your saved collections. At the bottom-right you'll see a
   panel with three buttons:
   - **"⬇️ Download entire collection"** — automatically scrolls through the
     collection (Facebook loads more videos as you reach the bottom),
     collects all videos and starts the download with `yt-dlp`.
   - **"📥 Send visible videos"** — sends only the videos currently on screen.
   - **"↩ Close Facebook"** — closes the Facebook window; Facebook Collections Downloader
     stays open.
4. You'll see a green notice when the download starts. Its **progress is
   visible live** in the Facebook Collections Downloader window: the **Facebook** tab shows
   the per-video list with percentage bars, and while downloading a
   **bottom indicator** is also visible from any tab (clicking it takes you
   to the list). When finished, the videos are in your folder and appear in
   the **Library**.

For downloads to work, install `yt-dlp` (only needed once):

```bash
sudo apt install yt-dlp
```

> 🔑 **Private collections**: your saved lists are private, but the button
> reads them anyway because it runs inside your logged-in session. To
> **download** those videos, on capture the app exports your session cookies
> to `data/cookies/fb_cookies.txt` and passes them to `yt-dlp`, which
> downloads using your session (not the browser). If the cookies expire, just
> open Facebook from the app and capture again: they refresh automatically.

> 🔒 **Local HTTPS**: the app is served over HTTPS with a self-signed
> certificate (generated automatically with `openssl` in `data/cert/`). This
> is necessary because Facebook is HTTPS and WebKitGTK blocks requests from a
> secure page to `http://127.0.0.1` (mixed content). Everything stays local:
> the server only listens on 127.0.0.1.

> 📡 **How videos are sent to the app**: Facebook enforces a security policy
> (CSP) that forbids any of its pages from making *fetch* requests to
> `127.0.0.1`. That's why the floating button **doesn't use HTTP**: it sends
> videos through the **native WebKit channel** (the internal bridge of
> pywebview), which reaches the app directly without going through the
> network. Neither CSP, CORS, nor mixed content can block it.

### 🖱️ Manual alternative (without the Facebook tab)

If you prefer the 100% manual method, you can also:

1. On Facebook, open the video and click **right-click → "Save video as…"**
   (or use a standalone downloader like `yt-dlp` by pasting the URL).
2. Place the files in the app's video folder (default:
   `~/Videos/Recetas`).
3. Open Facebook Collections Downloader, click **Scan** and the video appears in the Library.

In that case, the Facebook tab also offers a *bookmarklet* you can drag to
your browser's bookmarks bar to capture from there.

> ⚠️ The importer navigates Facebook with your account (just as you would
> manually) and only collects the videos **you** see on screen; it doesn't
> crawl your profile or anyone else's. As with any automation, use it in
> moderation to avoid drawing attention to your account.

---

## 2. What you need before starting

- **Python 3.10 or later** (most modern Linux distributions include it).
- A **terminal** (the small window where you type commands).
- **Internet connection** the first time (to download the transcription
  engine and the language model).

To check if you have Python, open a terminal and type:

```bash
python3 --version
```

If you see something like `Python 3.11.x` or later, you're good to go. If
you get an error or it says `venv` is missing, see section
[9. Troubleshooting](#9-troubleshooting).

---

## 3. What are `venv` and `pip`? (explained without jargon)

Think of a Python program like a recipe: it needs several "ingredients"
(packages) to work: Flask, Pillow, the transcription engine, etc.

- **`pip`** is the tool that downloads and installs those ingredients.
- **`venv`** (virtual environment) is an **isolated box** inside your project
  where those ingredients are stored, without touching the rest of the system.

Why is this box needed? Because almost all of Facebook Collections Downloader's ingredients are
available as Linux distribution packages... **except one**: the transcription
engine (`faster-whisper`). That one can only be installed with `pip`, and the
right way is to install it inside its box (`venv`), not system-wide. That way
nothing breaks, and if something goes wrong you just delete the box and
recreate it.

> The virtual environment folder is called `venv/` and lives inside the
> project folder. It can be deleted and recreated anytime: your recipe data
> is in a different folder (`data/`) and is not lost.

---

## 4. Installation step by step

Open a terminal and run the commands **one at a time**, pressing Enter after
each one.

**Step 1 — Go to the project folder.** (Change the path to yours if you
installed the project elsewhere.)

```bash
cd ~/Dev3/recipe_book_downloader
```

**Step 2 — Create the virtual environment (the "box").** This is done **only
once**, on the first installation.

```bash
python3 -m venv venv
```

If everything went well, you won't see any message. That's normal.

**Step 3 — Activate the virtual environment.** Notice the `(venv)` at the
beginning of the line: that's the signal you're inside the box.

```bash
source venv/bin/activate
```

**Step 4 — Install the ingredients.** This downloads and installs everything
the program needs (it may take a few minutes the first time).

```bash
pip install -r requirements.txt
```

**Step 5 — Launch the program.**

```bash
python run.py
```

The **Facebook Collections Downloader** window will open. 🎉

---

## 5. Activating and deactivating the virtual environment

The virtual environment is **activated** when you want to use `pip` or
`python` inside it, and **deactivated** when you're done.

### 🔓 Activate

```bash
source venv/bin/activate
```

You'll see `(venv)` at the beginning of the terminal line:

```
(venv) user@machine:~/Dev3/recipe_book_downloader$
```

As long as `(venv)` is there, `python` and `pip` commands use the project
environment. When you close the window, it deactivates automatically.

### 🔒 Deactivate

```bash
deactivate
```

The `(venv)` disappears from the line and you're back to the normal system.
(If you haven't activated it before, there's nothing to deactivate.)

### 🤓 Tip: you don't need to activate to use the app

To **launch the program** you don't need to activate anything. This command
always works, wherever you are (as long as you're in the project folder):

```bash
venv/bin/python run.py
```

It's the same app, no extra steps. Many people use it this way directly.

---

## 6. How to use the program

### Option A — native desktop window (recommended)

```bash
venv/bin/python run.py
```

![](images/01-recipe_book_downloader.png)

### Option B — in the browser

```bash
venv/bin/python run.py --web
```

### Option C — server only (for testing / API)

```bash
venv/bin/python run.py --serve --port 8765
```

**About the first transcription:** the first time you click *Transcribe*,
the program downloads the language model (~460 MB for the default *small*
model, saved to `~/.cache/huggingface`). It only happens once. If your
computer is modest, you can choose the *tiny* or *base* model in
**Settings** to make it faster (at the cost of some accuracy).

---

## 7. Features

- **Library**: cards with thumbnails, search by title/text and filters by
  category and status.
- **Recipe editor**: video player, live-editable transcription, ingredient
  and step lists, tags, notes and `.md` export.
- **Transcription queue**: real-time progress, cancellation and retry.
- **Settings**: video folder, Whisper model, language, CPU threads and VAD.
- **Import**: drag videos onto the window to copy them to your folder.
- **Facebook**: opens in its **own window** (Facebook Collections Downloader stays open),
  captures your saved videos with your own session and downloads them with
  `yt-dlp` to your folder, with **live progress** from any tab.

---

## 8. How to update the program

When there's a new version:

```bash
cd ~/Dev3/recipe_book_downloader
git pull
source venv/bin/activate
pip install -r requirements.txt
```

(`git pull` downloads the new code and `pip install` updates the ingredients
if needed.)

---

## 9. Troubleshooting

| Problem | Solution |
|---|---|
| `python3: command not found` | Install Python: `sudo apt install python3` |
| `ensurepip is not available` or `venv` is missing | Install the module: `sudo apt install python3-venv` and repeat Step 2 |
| `error: externally-managed-environment` | This is normal on Debian/MX: it means pip shouldn't touch the system. **Activate the venv** (Step 3) and repeat Step 4 |
| The venv is "broken" or something weird happens | Delete it and recreate: `rm -rf venv` and repeat steps 2–4. Your recipes are not lost (they're in `data/`) |
| Transcription takes too long | Choose a smaller model in **Settings** (tiny or base) |
| Model download fails halfway | Try again: it resumes where it left off. If it always fails, check your connection or proxy |
| Private Facebook videos won't download (authentication error) | The cookies expired. Open Facebook from the app and capture again: the app refreshes them automatically |
| I don't see download progress | While downloading, there's a bottom indicator on any tab; the full per-video list is in the Facebook tab |

---

## 10. Project structure

```
app/            Backend (Flask, SQLite, Whisper, video scanner)
web/            Interface (HTML/CSS/JS, no external frameworks)
data/           Database, thumbnails and settings (created on first use)
venv/           Virtual environment (DO NOT touch manually; created in Step 2)
run.py          Entry point
```

Everything is **local and private**: SQLite database and transcription on
your CPU, with nothing sent to the internet (except the initial language
model download).

---

## 11. Technologies under the hood (for CS students)

This section explains **what powers each part** of the program. If you already
code or are studying computer science, here's the map: what technology does
what, why it was chosen, and where it lives in the code.

> **The architectural idea in one sentence:** Facebook Collections Downloader is a *local
> client-server application*. A Python process launches a web server that
> only listens on `127.0.0.1`, and the interface is a web page (HTML/CSS/JS)
> served by that same server. The "native window" on the desktop is, in
> reality, an **embedded browser** pointing to that local URL. None of this
> needs the internet to work.

### 11.1 Backend: Python 3.10+ and Flask

- **Flask** is a Python micro-framework for HTTP. Here it defines a **REST
  API** returning JSON: `GET /api/recipes`, `POST /api/recipes/<id>/transcribe`,
  `POST /api/settings`… Each route is a Python function decorated with
  `@app.get(...)` / `@app.post(...)` (see `app/server.py`).
- **Werkzeug** (Flask's foundation) serves the app with
  `make_server(threaded=True)`: a **multi-threaded WSGI server** where each
  HTTP request is handled in its own thread (`run.py`).
- The same server serves the **static frontend** (`web/`) and **videos**
  (`/media/video/<id>`) with support for **HTTP Range requests** (responses
  `206 Partial Content`): this is what allows *seeking* in the video player
  without downloading the entire file.
- The `after_request` middleware controls **CORS** only on `/api/fb/*`,
  accepting only Facebook origins or the app's own origin (see 11.8).

### 11.2 Persistence: SQLite (embedded, no ORM)

- **SQLite** is an **embedded** database: there's no separate database
  process, everything lives in a single file (`data/recipes.db`). Perfect for
  a single-user local app.
- It uses Python's standard `sqlite3` module, with `check_same_thread=False`
  because multiple threads access the same connection, and a
  `threading.Lock` protects every write operation (`app/database.py`).
- Lists (`tags`, `ingredients`, `steps`) are stored as **JSON text** and
  serialized/deserialized with `json.dumps` / `json.loads`.
- Accent-insensitive search is achieved by **normalizing text to Unicode NFD**
  and stripping diacritics before comparing.
- Indexes on `status` and `category` keep library filters fast even with
  thousands of recipes.

### 11.3 Local transcription: Whisper (faster-whisper)

- **Whisper** is an AI model from OpenAI for **transcribing audio to text**
  (published in the paper *"Robust Speech Recognition via Large-Scale Weak
  Supervision"*). It's a **transformer encoder-decoder** trained on hundreds
  of thousands of hours of audio with subtitles, supporting ~99 languages.
- **faster-whisper** is a reimplementation built on **CTranslate2** (an
  inference engine optimized for CPU/GPU). Here it runs with
  `compute_type="int8"` (**8-bit integer quantization**: ~4× faster and
  less memory than float32, with minimal accuracy loss) and `cpu_threads`
  for parallelization (`app/transcription.py`).
- Before transcribing, a **VAD** (Voice Activity Detection, from Silero)
  discards silence and background music: in cooking videos this prevents
  text hallucinations during silent parts.
- Decoding uses **beam search**; the model returns *segments* with timestamps
  that the app streams to the database in real time.
- The `tiny`/`base`/`small`/`medium` sizes are different parameter counts of
  the same Whisper model: larger = more accurate, but slower and more memory
  (the default `small` is ~460 MB, downloaded from **Hugging Face** on first
  use to `~/.cache/huggingface`).

### 11.4 The native window: pywebview and WebKitGTK

- **pywebview** creates desktop windows with a real web engine inside
  (**WebKitGTK** on Linux, WebView2/WebKit on other platforms). It allows
  combining a web interface with Python APIs.
- Its **native bridge** (`js_api`, the `jsBridge` channel) lets JavaScript on
  a page call Python methods **without going through HTTP**. This is the key
  piece of the Facebook importer: Facebook's CSP blocks `fetch` to
  `127.0.0.1`, but it cannot block this internal channel (`app/window.py` and
  the capture script in `app/fb.py`).
- The floating button injection uses **WebKit user scripts**: scripts
  registered to run at `document-start` of *every* page loaded in the window,
  with a guard that only activates on `facebook.com`.
- With `private_mode=False` and `storage_path`, the session (cookies)
  survives app restarts; it's stored in `data/webview/`.
- A notable concurrency detail: WebKitGTK **is only safe from the main
  thread**, so operations from Python threads are scheduled with
  `GLib.idle_add` (see `_navigate_later` in `app/window.py`).

### 11.5 Video downloads: yt-dlp

- **yt-dlp** (an active fork of youtube-dl) is a **CLI written in Python**
  capable of downloading videos from hundreds of sites, including Facebook.
- The app launches it as a **subprocess** (`subprocess.Popen`) and reads its
  output live to show progress: each `[download] N%` line is parsed with a
  regex and stored in the download queue (`app/fb.py`).
- For **private collections**, it exports the webview session cookies to a
  file in **Netscape format** and passes them to `yt-dlp` with `--cookies`
  (the format that tool expects).
- Cancellation is handled by a **watchdog thread** that calls
  `proc.terminate()` when the user clicks Stop (necessary because yt-dlp's
  output may be buffered and not reach the reading loop).

### 11.6 Metadata and thumbnails: PyAV, ffmpeg and Pillow

- **PyAV** (Python bindings for the **FFmpeg** libraries) opens the video to
  read its **duration** and extract the **first frame**.
- **Pillow** resizes that frame and saves it as JPEG (the thumbnail on the
  recipe card).
- If PyAV isn't available, there's a *fallback* to system binaries `ffprobe`
  and `ffmpeg` (`app/scanner.py`).

### 11.7 Frontend: HTML, CSS and JavaScript (no frameworks)

- There's no React or Vue: the interface is **vanilla JS** (`"use strict"`).
  The DOM is built with *template literals*, values are escaped with `esc()`
  to prevent HTML injection, and API calls use **fetch** with JSON.
- "Real-time" is achieved by **polling**: a `setInterval` checks the status
  every 1.5 seconds (`/api/transcription/jobs`, download status, …) and
  re-renders what changed. It's the simple solution; for this data volume
  there's no need for WebSocket or SSE.
- The player is an HTML `<video>` tag fed by the `/media/video/<id>`
  endpoint with Range support (see 11.1).

### 11.8 Concurrency and web security, applied for real

This project is a great case study because it brings together several
concepts that can feel like theory in class:

- **Mixed content:** an HTTPS page cannot make requests to
  `http://127.0.0.1`. Since Facebook is HTTPS, the app serves itself over
  **local HTTPS with a self-signed certificate** (generated with `openssl`
  in `data/cert/`). A self-signed certificate is valid for localhost, but
  browsers would reject it on any other site.
- **CSP (Content-Security-Policy):** Facebook forbids its pages from making
  `fetch` requests to local addresses. That's why the floating button sends
  videos through the **native pywebview channel** (jsBridge), which isn't an
  HTTP request and isn't subject to CSP.
- **CORS, CSRF and DNS-rebinding:** the local server accepts requests from
  Facebook or from the app itself, and rejects any other origin (`Origin`).
  This way a malicious web page can't trick your local server into downloading
  videos without your permission.
- **The server only listens on `127.0.0.1`**: there are no ports open to the
  network. The only outbound traffic from your machine is the initial model
  download (from Hugging Face) and yt-dlp video downloads.

### 11.9 Where downloaded files are stored (path map)

A very common question: "where was this downloaded to?". Here's the complete
map. It splits into two locations: **inside the project** (the `data/`
folder, created on first use) and **outside, in your user folder** (caches
and videos).

| Path | What it contains | How it gets there |
|---|---|---|
| `data/recipes.db` | SQLite database: recipes, transcriptions, status | Created and written by the app |
| `data/thumbs/` | JPEG thumbnails for each video (`thumb_<id>.jpg`) | Generated by the app with PyAV/Pillow |
| `data/settings.json` | Settings: video folder, model, language, threads, VAD | Saved by you from **Settings** |
| `data/webview/` | Embedded browser profile: cookies and Facebook session | Persisted by pywebview (`private_mode=False`); if you delete it you'll need to log in again |
| `data/cookies/fb_cookies.txt` | Your Facebook session cookies in Netscape format, for `yt-dlp` | Exported from the webview on each capture (private collections) |
| `data/cert/` | Self-signed HTTPS certificate (`cert.pem`, `key.pem`) | Generated by `openssl` on first run (`run.py`) |
| `venv/` | All Python packages installed via pip (Flask, faster-whisper, pywebview…) | Created with `python3 -m venv venv` and `pip install -r requirements.txt` |
| `venv/lib/python3.*/site-packages/faster_whisper/assets/silero_vad.onnx` | **Silero VAD** model (voice detection) | **Bundled inside** the faster-whisper pip package; not downloaded separately |
| `~/.cache/huggingface/hub/models--Systran--faster-whisper-small/` | Whisper **small** model (~460 MB) | Downloaded from **Hugging Face** on your first transcription. The folder name changes with the chosen model (`...faster-whisper-tiny/`, `...-base/`, `...-medium/`) |
| `~/Videos/Recetas` | **Downloaded videos** from Facebook via yt-dlp | The watched folder; configurable in **Settings**. This is where the app looks for new videos |

**What can be safely deleted and what can't:**

- `data/` is **your information** (recipes, transcriptions, Facebook
  session): it's not touched if you reinstall. It's the only thing worth
  **backing up**.
- `venv/` can be deleted and recreated anytime (steps 2–4 of installation):
  your data isn't stored there. Same goes for `data/cert/` (regenerated
  automatically) and `data/cookies/` (refreshed on next capture).
- `~/.cache/huggingface/` is just cache: if you delete it, the Whisper model
  will be **re-downloaded** on the next transcription (~460 MB, only once).
- The videos in `~/Videos/Recetas` are **your files**: deleting them from the
  app (delete button) or manually removes them from disk; the database keeps
  the reference, which is how the app detects when a video "no longer exists".

### 11.10 For further reading

If you want to study the code, here's the recommended order:

```
run.py                  → how everything starts (server, HTTPS, window)
app/server.py           → the REST API and media server
app/database.py         → persistence layer (SQLite + threads)
app/transcription.py    → Whisper: model, VAD, queue and cancellation
app/window.py           → pywebview: native bridge and user scripts
app/fb.py               → yt-dlp, Netscape cookies and capture script
web/app.js              → frontend: fetch, polling and DOM rendering
```

Official documentation for the key pieces:
[Flask](https://flask.palletsprojects.com/),
[SQLite](https://www.sqlite.org/docs.html),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[pywebview](https://pywebview.flowrl.com/),
[yt-dlp](https://github.com/yt-dlp/yt-dlp),
and the [Whisper paper](https://cdn.openai.com/papers/whisper.pdf).

---

## 12. Internationalization (i18n)

Facebook Collections Downloader supports multiple languages using
**Qt Linguist `.ts` files** (XML-based translation format). The base language
is English; translations are loaded at runtime.

### How it works

| Layer | Mechanism |
|---|---|
| Backend (Python) | `app/i18n.py` parses `.ts` XML files and provides `tr(context, source)` |
| Frontend (JS) | `web/i18n.js` loads translations via `GET /api/translations/<lang>` and applies them to DOM elements with `data-i18n` attributes |
| Translation files | `locale/en.ts` (English source, 141 strings), `locale/es.ts` (Spanish) |
| Compiled files | `locale/*.qm` generated by `lrelease` (optional, for Qt-based tools) |

### Adding a new language

1. Copy `locale/en.ts` to `locale/xx.ts` (where `xx` is the ISO 639-1 code).
2. Translate every `<translation>` element in the new file.
3. Compile: `lrelease locale/xx.ts -qm locale/xx.qm`
4. The app detects the new `.ts` file automatically and offers it in Settings.

### Editing translations with Qt Creator / Qt Linguist

To edit `.ts` files visually with the **Qt Linguist** GUI (included in
Qt Creator):

```bash
# Debian/Ubuntu — install the tools (one-time)
sudo apt install qt6-l10n-tools linguist-qt6 qtcreator

# Open a .ts file in Linguist
linguist locale/es.ts

# Or open the whole project in Qt Creator (File → Open File → locale/es.ts)
```

**Qt Creator** has a built-in translation editor: open a `.ts` file and it
shows a table with source strings on the left and translation fields on the
right. You can mark translations as *finished*, *unfinished*, or *obsolete*.

**Required packages for Linux developers:**

| Package | What it provides | Install command |
|---|---|---|
| `qt6-l10n-tools` | `lupdate` (extract strings) + `lrelease` (compile .qm) | `sudo apt install qt6-l10n-tools` |
| `linguist-qt6` | Qt Linguist GUI editor | `sudo apt install linguist-qt6` |
| `qtcreator` | Qt Creator IDE with integrated Linguist | `sudo apt install qtcreator` |

For Qt 5 instead of Qt 6: replace `qt6-l10n-tools` with `qttools5-dev-tools`
and `linguist-qt6` with `qttools5-dev`.

### Extracting strings from source code

```bash
# Extract Python strings into a .ts file
pylupdate6 app/*.py -ts locale/template.ts

# Update an existing .ts file with new/changed strings
lupdate web/app.js web/index.html -ts locale/en.ts
```

### File structure

```
locale/
  en.ts       ← English source strings (141 strings, 7 contexts)
  es.ts       ← Spanish translations
  en.qm       ← compiled (generated by lrelease, git-ignored)
  es.qm       ← compiled (generated by lrelease, git-ignored)
```

### Contexts in the .ts files

| Context | Contains |
|---|---|
| `MainWindow` | Brand, navigation, footer |
| `Library` | Library view (search, filters, cards) |
| `Queue` | Transcription queue |
| `Facebook` | Facebook import tab |
| `Settings` | Settings panel |
| `Editor` | Recipe editor |
| `Toasts` | Toast notification messages |
| `Backend` | Python error/info messages |
