import subprocess
import time

cmd = [
    "/home/wachin/.local/bin/yt-dlp",
    "--no-playlist", "--no-warnings", "--newline", "--retries", "3",
    "--print", "after_move:filepath",
    "-o", "/tmp/fbdl_out2/%(title).80s [%(id)s].%(ext)s",
    "http://127.0.0.1:8897/big.mp4",
]
proc = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1,
)
start = time.time()
count = 0
for line in proc.stdout:
    count += 1
    if count <= 4 or count % 20 == 0:
        print(f"[{time.time()-start:6.1f}s] n={count}: {line.rstrip()[:80]}", flush=True)
    if time.time() - start > 12:
        proc.terminate()
        print("terminando tras 12s", flush=True)
        break
print(f"total lineas leidas: {count}", flush=True)
