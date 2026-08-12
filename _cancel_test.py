import time

from app import config, database as db, fb

config.settings["watch_folder"] = "/tmp/fbdl_out3"
db.fb_add_urls(["http://127.0.0.1:8896/big.mp4"])
fid = db.fb_list()[0]["id"]
print("id capturado:", fid)
ok, msg = fb.downloader.start([fid])
print("start:", ok, msg)
time.sleep(4)
cancelled = fb.downloader.cancel()
print("cancel devolvió:", cancelled)
t0 = time.time()
while time.time() - t0 < 20:
    st = fb.downloader.status()
    if not st["running"]:
        break
    time.sleep(0.5)
st = fb.downloader.status()
print("running final:", st["running"])
for it in st["items"]:
    print(" status:", it["status"], "| progress:", round(it["progress"]), "% | err:", it["error"][:80])
