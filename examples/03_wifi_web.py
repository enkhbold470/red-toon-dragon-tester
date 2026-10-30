# Control the eyes from your phone: connects to Wi-Fi and serves a color picker.
# Put your network in secrets.py on the board (see secrets_example.py), then
#   python dev.py run examples/03_wifi_web.py
# and open the printed http://<ip>/ address on any device on the same network.
import socket
import dragon
from secrets import WIFI_SSID, WIFI_PASSWORD

ip = dragon.wifi(WIFI_SSID, WIFI_PASSWORD)
print("open http://%s/" % ip)
dragon.eyes.blink("green", times=2)

PAGE = """<!doctype html><meta name=viewport content="width=device-width">
<body style="font-family:system-ui;text-align:center;padding:40px">
<h1>Toon Dragon eyes</h1><input type=color id=c value="#ff0000" style="width:200px;height:120px">
<script>c.oninput=()=>fetch('/set?'+c.value.slice(1))</script>"""

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 80))
s.listen(2)
while True:
    conn, _ = s.accept()
    try:
        req = conn.recv(512).decode()
        path = req.split(" ")[1] if " " in req else "/"
        if path.startswith("/set?"):
            h = path[5:11]
            try:
                rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            except ValueError:   # not a #rrggbb color: refuse it instead of crashing the server
                conn.send(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                continue
            dragon.eyes.color(rgb)
            conn.send(b"HTTP/1.0 204 No Content\r\n\r\n")
        else:
            conn.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + PAGE.encode())
    finally:
        conn.close()
