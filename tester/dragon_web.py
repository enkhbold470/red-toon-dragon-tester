#!/usr/bin/env python3
"""Browser GUI for the Red Eyes Toon Dragon test station (standard library only).

    python tester/dragon_web.py                 # opens http://127.0.0.1:8765
    python tester/dragon_web.py --listen 0.0.0.0:8765   # reachable from other machines on the LAN
"""
import csv, json, os, queue, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dragon_tester as dt

HERE = os.path.dirname(os.path.abspath(__file__))


class WebUI:
    """Broadcasts test events to every open browser tab and waits for answers."""

    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []      # one Queue per open /events stream
        self.history = []      # events for the current board, replayed to new tabs
        self.answer = queue.Queue()
        self.pending = None    # the open question, if any

    def emit(self, kind, text="", **data):
        ev = {"kind": kind, "text": text, "t": time.time(), **data}
        with self.lock:
            if kind == "board":
                self.history = []
            self.history.append(ev)
            for q in self.clients:
                q.put(ev)
        if kind in dt.ConsoleUI.STYLE or kind == "result":   # mirror to the terminal
            dt.ConsoleUI().emit(kind, text, **data)

    def ask(self, question, choices):
        while not self.answer.empty():
            self.answer.get_nowait()
        self.pending = {"question": question, "choices": choices}
        self.emit("ask", question, choices=choices)
        while True:
            a = self.answer.get()
            if a in choices:
                break
        self.pending = None
        self.emit("answered", a)
        return a

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            for ev in self.history:
                q.put(ev)
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)


class Station:
    """The batch loop from dragon_tester, in a thread that can be started and stopped."""

    def __init__(self, base_args):
        self.base = base_args
        self.thread = None
        self.stop = threading.Event()
        self.state = "idle"
        self.settings = {}

    def set_state(self, state, text):
        self.state = state
        dt.ui.emit("status", text, state=state)

    def start(self, settings):
        if self.thread and self.thread.is_alive():
            return False
        args = dt.build_parser().parse_args([])
        args.csv, args.port, args.app_offset = self.base.csv, self.base.port, self.base.app_offset
        args.app = self.base.app
        args.note = settings.get("note") or None
        args.auto = bool(settings.get("auto"))
        args.no_flash = bool(settings.get("no_flash"))
        args.skip_uart_pins = bool(settings.get("skip_uart_pins"))
        args.min_rssi = int(settings.get("min_rssi") or -85)
        self.settings = settings
        self.stop.clear()
        self.thread = threading.Thread(target=self.loop, args=(args,), daemon=True)
        self.thread.start()
        return True

    def loop(self, args):
        try:
            while not self.stop.is_set():
                self.set_state("waiting", "Plug in a board")
                port = None
                while not port and not self.stop.is_set():
                    port = args.port or dt.wait_for_port(1)
                if self.stop.is_set():
                    break
                board_no = dt.next_board_no(args.csv)
                self.set_state("testing", f"Testing board #{board_no}")
                res, det, mac, log = dt.do_board(args, port, board_no)
                dt.record(args, board_no, mac, res, det, log)
                dt.summarize(board_no, res)
                self.set_state("unplug", "Unplug the board")
                while port in dt.esp_ports() and not self.stop.is_set():
                    time.sleep(0.3)
                if args.port:   # fixed port: we can't see unplugging, wait for the operator
                    dt.ui.ask("Swap in the next board, then continue", ["next"])
        except Exception as e:
            dt.ui.emit("fail", f"station error: {e!r}")
        finally:
            self.set_state("idle", "Stopped")


def read_results(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def make_handler(station, ui):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if self.path == "/":
                with open(os.path.join(HERE, "web", "index.html"), "rb") as f:
                    self.send(200, f.read(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self.send(200, {"state": station.state, "settings": station.settings,
                                "pending": ui.pending, "ports": dt.esp_ports(),
                                "csv": station.base.csv, "app": station.base.app})
            elif self.path == "/api/results":
                self.send(200, read_results(station.base.csv))
            elif self.path == "/api/events":
                self.events()
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/api/start":
                self.send(200, {"started": station.start(self.body())})
            elif self.path == "/api/stop":
                # takes effect between boards; a board under test is finished first
                station.stop.set()
                if ui.pending and ui.pending["choices"] == ["next"]:
                    ui.answer.put("next")
                self.send(200, {"stopping": True})
            elif self.path == "/api/answer":
                ui.answer.put(str(self.body().get("value", "")))
                self.send(200, {"ok": True})
            else:
                self.send(404, {"error": "not found"})

        def events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q = ui.subscribe()
            try:
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                ui.unsubscribe(q)
    return H


def serve(args):
    ui = WebUI()
    dt.ui = ui
    station = Station(args)
    host, _, port = args.listen.rpartition(":")
    httpd = ThreadingHTTPServer((host or "127.0.0.1", int(port)), make_handler(station, ui))
    httpd.daemon_threads = True
    url = f"http://{'127.0.0.1' if host in ('', '0.0.0.0') else host}:{port}"
    print(f"Dragon test station running at {url}  (Ctrl-C to quit)")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    a = dt.build_parser().parse_args(["web"] + sys.argv[1:])
    serve(a)
