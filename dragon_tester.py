#!/usr/bin/env python3
"""Flash + test station for the Red Eyes Toon Dragon board (ESP32-C6-MINI-1U).

    python dragon_tester.py              # batch: plug a board, it flashes + tests, repeat
    python dragon_tester.py test         # test the board that's plugged in (no flashing)
    python dragon_tester.py info         # chip / MAC / flash info only
    python dragon_tester.py flash        # flash MicroPython only
    python dragon_tester.py monitor      # serial console (Ctrl-] to quit)

Results go to results.csv (one row per board) and logs/<mac>.log.
"""
import argparse, csv, datetime, hashlib, json, os, subprocess, sys, time, urllib.request

import serial
from serial.tools import list_ports

HERE = os.path.dirname(os.path.abspath(__file__))
ESPRESSIF_VID = 0x303A

FW_NAME = "ESP32_GENERIC_C6-20260824-v1.29.0.bin"
FW_URL = "https://micropython.org/resources/firmware/" + FW_NAME
FW_SHA256 = "3688ba4e2c3949e639f5772e99fdb0efa1258b162a496133f78c108434195c89"

# Where each test points you when it fails (refs are from the KiCad design).
HINTS = {
    "usb": "No ESP32-C6 on USB. Check J1 USB-C solder (D+/D- = A6/B6, A7/B7), U3 USBLC6, "
           "F1 fuse, D4 diode, U2 AP2112K 3V3 regulator. Try: hold BOOT, tap RESET, release BOOT.",
    "flash": "Flashing failed. Hold BOOT (SW2), tap RESET (SW1), release BOOT, then retry. "
             "If it keeps failing, check U1 module soldering and the 3V3 rail (U2, C13, C3).",
    "repl": "Board flashed but MicroPython did not answer. Press RESET (SW1) and retry `test`.",
    "chip": "Flash smaller than 4 MB or chip info failed - wrong module variant on U1?",
    "gpio": "Header pin problem: look for solder bridges / shorts on J3, J4 and the U1 module pads.",
    "leds": "RGB LEDs: D1 data is GPIO8 (U1 pad 22, R7 pull-up), D1 DOUT -> D2 DIN. "
            "If D1 works but D2 doesn't, check the D1->D2 link. Both dead: 5V rail (D4, F1) or D1. "
            "PWR LED dark: D3, R11, and solder jumper JP1 must be bridged.",
    "boot": "BOOT button (SW2, GPIO9, R6 10k pull-up) not seen. Check SW2 soldering.",
    "reset": "RESET button (SW1, EN, R5 10k + C10 1uF) did not reset the chip. Check SW1 soldering.",
    "i2c": "Qwiic J2: SDA=GPIO0, SCL=GPIO14. No pull-ups on the board - your sensor must have them.",
    "wifi": "No Wi-Fi networks seen. This is the -1U module: plug an antenna into the U.FL connector.",
}

# GPIO number -> header pin label, for readable short/bridge reports
PIN_LABEL = {7: "J3.1 IO7", 6: "J3.2 IO6", 5: "J3.3 IO5", 4: "J3.4 IO4", 3: "J3.5 IO3",
             2: "J3.6 IO2", 1: "J3.7 IO1", 0: "J3.8 SDA/IO0", 14: "J3.9 SCL/IO14",
             23: "J4.1 IO23", 22: "J4.2 IO22", 21: "J4.3 IO21", 20: "J4.4 IO20",
             19: "J4.5 IO19", 18: "J4.6 IO18", 17: "J4.7 RX/IO17", 16: "J4.8 TX/IO16"}

TESTS = ["chip", "gpio", "leds", "boot", "reset", "wifi", "i2c"]

# ---------------------------------------------------------------- output

def c(code, s):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s

def ok(s):   print(c("32", "  PASS ") + s)
def bad(s):  print(c("31", "  FAIL ") + s)
def note(s): print(c("33", "  .... ") + s)
def step(s): print(c("1;36", "\n== " + s))

# ---------------------------------------------------------------- ports

def esp_ports():
    return [p.device for p in list_ports.comports() if p.vid == ESPRESSIF_VID]

def wait_for_port(timeout=None, exclude=()):
    t0 = time.time()
    while timeout is None or time.time() - t0 < timeout:
        ports = [p for p in esp_ports() if p not in exclude]
        if ports:
            return ports[0]
        time.sleep(0.3)
    return None

def wait_for_unplug(port):
    while port in esp_ports():
        time.sleep(0.3)

# ---------------------------------------------------------------- firmware / esptool

def firmware_path():
    path = os.path.join(HERE, "firmware", FW_NAME)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        note(f"downloading {FW_URL}")
        urllib.request.urlretrieve(FW_URL, path + ".part")
        os.replace(path + ".part", path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != FW_SHA256:
        os.remove(path)
        sys.exit(f"firmware checksum mismatch ({digest}); deleted, run again to re-download")
    return path

def esptool(port, *args):
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32c6", "--port", port,
           "--baud", "921600", *args]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0, p.stdout + p.stderr

def chip_info(port):
    good, out = esptool(port, "--after", "hard-reset", "flash-id")
    info = {}
    for line in out.splitlines():
        if line.startswith("BASE MAC:"):
            info["mac"] = line.split(":", 1)[1].strip()
        elif "Detected flash size:" in line:
            info["flash"] = line.split(":", 1)[1].strip()
        elif line.startswith("Chip type:") or line.startswith("Chip is "):
            info["chip"] = line.split(":", 1)[-1].strip()
    return good, info, out

def flash(port, image, offset="0x0", erase=True):
    args = ["write-flash", "-z"] + (["--erase-all"] if erase else []) + [offset, image]
    return esptool(port, *args)

# ---------------------------------------------------------------- MicroPython raw REPL

class Board:
    def __init__(self, port):
        self.port = port
        self.ser = None

    def open(self, timeout=15):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                self.ser = serial.Serial(self.port, 115200, timeout=0.2)
                self._enter_raw()
                return True
            except (serial.SerialException, OSError, TimeoutError):
                self.close()
                time.sleep(0.5)
        return False

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def _read_until(self, marker, timeout):
        buf, t0 = b"", time.time()
        while not buf.endswith(marker):
            if time.time() - t0 > timeout:
                raise TimeoutError(f"waiting for {marker!r}, got {buf[-200:]!r}")
            buf += self.ser.read(1)
        return buf

    def _enter_raw(self):
        self.ser.write(b"\r\x03\x03")
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\x01")
        self._read_until(b"raw REPL; CTRL-B to exit\r\n>", 5)

    def exec(self, code, timeout=20):
        data = code.encode()
        for i in range(0, len(data), 256):
            self.ser.write(data[i:i + 256])
            time.sleep(0.01)
        self.ser.write(b"\x04")
        self._read_until(b"OK", 5)
        out = self._read_until(b"\x04", timeout)[:-1]
        err = self._read_until(b"\x04", timeout)[:-1]
        self._read_until(b">", timeout)
        if err:
            raise RuntimeError(err.decode(errors="replace").strip())
        return out.decode(errors="replace")

    def run(self, name, *args, timeout=20):
        a = ", ".join(repr(x) for x in (name,) + args)
        out = self.exec(f"run({a})", timeout)
        for line in out.splitlines():
            if line.startswith("@@"):
                return json.loads(line[2:])
        raise RuntimeError(f"no result from {name}: {out!r}")

    def load_tests(self):
        self.exec(open(os.path.join(HERE, "board_side.py")).read())

# ---------------------------------------------------------------- tests

def run_tests(port, args):
    """Returns (results dict test->bool/None, details dict)."""
    res, det = {}, {}
    b = Board(port)
    if not b.open():
        bad("MicroPython REPL not reachable")
        note(HINTS["repl"])
        res["repl"] = False
        return res, det
    try:
        b.load_tests()

        step("chip")
        r = b.run("chip"); det["chip"] = r
        res["chip"] = r.get("ok", False)
        (ok if res["chip"] else bad)(f"{r.get('flash_mb')} MB flash, {r.get('freq_mhz')} MHz, "
                                     f"temp {r.get('temp_c', '?')} C, {r.get('fw', '')}")
        if not res["chip"]:
            note(HINTS["chip"])

        step("header GPIO shorts / solder bridges")
        pins = [7, 6, 5, 4, 3, 2, 1, 0, 14, 23, 22, 21, 20, 19, 18]
        if not args.skip_uart_pins:
            pins += [17, 16]
        r = b.run("gpio", pins); det["gpio"] = r
        res["gpio"] = r.get("ok", False)
        if res["gpio"]:
            ok(f"{len(pins)} header pins clean (no shorts to GND/3V3, no bridges)")
        else:
            for n in r.get("stuck_low", []):  bad(f"{PIN_LABEL[n]} shorted to GND")
            for n in r.get("stuck_high", []): bad(f"{PIN_LABEL[n]} shorted to 3V3/5V")
            for x, y in r.get("bridges", []): bad(f"{PIN_LABEL[x]} bridged to {PIN_LABEL[y]}")
            if "error" in r: bad(r["error"])
            note(HINTS["gpio"])

        step("LEDs (look at the board)")
        if args.auto:
            b.run("leds_cycle"); res["leds"] = None; note("skipped check (--auto)")
        else:
            while True:
                b.run("leds_cycle")
                q = "Did BOTH RGB eyes go red -> green -> blue -> white, and is the PWR LED on? (r = repeat)"
                a = input(c("1;33", f"  ?  {q} [y/n/r] ")).strip().lower()
                if a != "r":
                    break
            res["leds"] = a in ("", "y", "yes")
            (ok if res["leds"] else bad)("LEDs")
            if not res["leds"]:
                note(HINTS["leds"])
        b.exec("leds(0, 0, 0)")

        step("BOOT button")
        if args.auto:
            res["boot"] = None; note("skipped (--auto)")
        else:
            print(c("1;33", "  >> press and release BOOT (SW2) ..."))
            b.exec("leds(0, 0, 40)")
            res["boot"] = wait_button(b, 15)
            b.exec("leds(0, 0, 0)")
            (ok if res["boot"] else bad)("BOOT button / GPIO9")
            if not res["boot"]:
                note(HINTS["boot"])

        step("Wi-Fi radio + antenna")
        r = b.run("wifi", timeout=30); det["wifi"] = r
        res["wifi"] = r.get("ok", False)
        if res["wifi"] and r["best_rssi"] < args.min_rssi:
            res["wifi"] = False
        msg = f"{r.get('count', 0)} networks, best RSSI {r.get('best_rssi')} dBm (min {args.min_rssi})"
        (ok if res["wifi"] else bad)(msg)
        if not res["wifi"]:
            note(r.get("error", "") or HINTS["wifi"])

        step("Qwiic / I2C (info only)")
        r = b.run("i2c"); det["i2c"] = r
        res["i2c"] = None
        note(f"devices on SDA=IO0/SCL=IO14: {', '.join(r.get('found', [])) or 'none'}"
             + (f" ({r['error']})" if "error" in r else ""))

        step("RESET button")
        if args.auto:
            res["reset"] = None; note("skipped (--auto)")
        else:
            b.exec("import time; leds(40, 0, 0); _t = time.ticks_ms()")
            print(c("1;33", "  >> press RESET (SW1) - the eyes should go dark ..."))
            res["reset"] = wait_reset(b, 20)
            (ok if res["reset"] else bad)("RESET button / EN")
            if not res["reset"]:
                note(HINTS["reset"])
    except Exception as e:
        bad(f"test crashed: {e}")
        res["repl"] = False
    finally:
        b.close()
    return res, det

def wait_button(b, timeout):
    t0, pressed = time.time(), False
    while time.time() - t0 < timeout:
        v = b.exec("print(boot_state())").strip()
        if v == "0":
            pressed = True
        elif pressed and v == "1":
            return True
        time.sleep(0.05)
    return False

def wait_reset(b, timeout):
    """Reset drops the board's USB link; afterwards the REPL state must be gone."""
    probe = "print('alive' if '_t' in globals() else 'fresh')"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if "fresh" in b.exec(probe, timeout=2):
                return True
        except Exception:
            b.close()
            time.sleep(0.5)
            port = wait_for_port(10)
            if not port:
                return False
            b.port = port
            return b.open(10) and "fresh" in b.exec(probe)
        time.sleep(0.3)
    return False

# ---------------------------------------------------------------- logging

def next_board_no(csv_path):
    if not os.path.exists(csv_path):
        return 1
    with open(csv_path) as f:
        nums = [int(r["board"]) for r in csv.DictReader(f) if r.get("board", "").isdigit()]
    return max(nums, default=0) + 1

def record(args, board_no, mac, res, det, flash_log):
    fields = ["time", "board", "mac", "result"] + TESTS + ["failed", "wifi_rssi", "notes"]
    failed = [k for k, v in res.items() if v is False]
    row = {"time": datetime.datetime.now().isoformat(timespec="seconds"),
           "board": board_no, "mac": mac, "result": "FAIL" if failed else "PASS",
           "failed": " ".join(failed), "wifi_rssi": det.get("wifi", {}).get("best_rssi", ""),
           "notes": args.note or ""}
    for t in TESTS:
        row[t] = {True: "pass", False: "FAIL", None: "-"}[res.get(t)]
    new = not os.path.exists(args.csv)
    with open(args.csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    with open(os.path.join(HERE, "logs", f"{mac.replace(':', '')}.log"), "a") as f:
        f.write(json.dumps({"row": row, "details": det}) + "\n" + flash_log + "\n")
    return row

# ---------------------------------------------------------------- one board

def do_board(args, port, board_no):
    print(c("1;35", f"\n######## board #{board_no} on {port} ########"))
    flash_log = ""
    step("chip info")
    good, info, out = chip_info(port)
    if not good:
        bad("esptool could not talk to the chip"); note(HINTS["usb"]); print(out[-800:])
        return {"usb": False}, {}, "unknown", out
    mac = info.get("mac", "unknown")
    ok(f"ESP32-C6  MAC {mac}  flash {info.get('flash', '?')}")

    if not args.no_flash:
        step("flash MicroPython test firmware")
        t0 = time.time()
        good, flash_log = flash(port, firmware_path())
        if not good:
            bad("flash failed"); note(HINTS["flash"]); print(flash_log[-800:])
            return {"flash": False}, {}, mac, flash_log
        ok(f"flashed in {time.time() - t0:.0f}s")
        port = wait_for_port(15) or port
        time.sleep(1.5)

    res, det = run_tests(port, args)

    if args.app and not any(v is False for v in res.values()):
        step(f"flash final app {os.path.basename(args.app)} @ {args.app_offset}")
        port = wait_for_port(15) or port
        good, log = flash(port, args.app, args.app_offset)
        res["app"] = good
        (ok if good else bad)("final firmware")
        flash_log += log
    return res, det, mac, flash_log

def summarize(board_no, res):
    failed = [k for k, v in res.items() if v is False]
    if failed:
        print(c("1;41", f"\n  BOARD #{board_no}: FAIL ({', '.join(failed)})  ") + "\n")
    else:
        print(c("1;42", f"\n  BOARD #{board_no}: PASS  ") + "\n")

# ---------------------------------------------------------------- commands

def cmd_batch(args):
    print(c("1", "Red Eyes Toon Dragon test station") + f"  ->  {args.csv}")
    print("Plug in a board (Ctrl-C to quit).")
    while True:
        port = args.port or wait_for_port()
        board_no = next_board_no(args.csv)
        res, det, mac, log = do_board(args, port, board_no)
        record(args, board_no, mac, res, det, log)
        summarize(board_no, res)
        if args.port:
            input("Swap the board and press Enter ...")
        else:
            print("Unplug the board ...")
            wait_for_unplug(port)
            print("Plug in the next board.")

def cmd_test(args):
    port = args.port or wait_for_port(5)
    if not port:
        sys.exit(HINTS["usb"])
    args.no_flash = True
    board_no = next_board_no(args.csv)
    res, det, mac, log = do_board(args, port, board_no)
    record(args, board_no, mac, res, det, log)
    summarize(board_no, res)

def cmd_info(args):
    port = args.port or wait_for_port(5)
    if not port:
        sys.exit(HINTS["usb"])
    good, info, out = chip_info(port)
    print(out if args.verbose or not good else json.dumps(info, indent=2))

def cmd_flash(args):
    port = args.port or wait_for_port(5)
    if not port:
        sys.exit(HINTS["usb"])
    image = args.app or firmware_path()
    good, out = flash(port, image, args.app_offset if args.app else "0x0")
    print(out[-1500:])
    sys.exit(0 if good else 1)

def cmd_monitor(args):
    port = args.port or wait_for_port(5)
    if not port:
        sys.exit(HINTS["usb"])
    from serial.tools import miniterm
    sys.argv = ["miniterm", port, "115200", "--raw"]
    miniterm.main()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="batch",
                    choices=["batch", "test", "info", "flash", "monitor"])
    ap.add_argument("--port", help="serial port (default: auto-detect Espressif USB)")
    ap.add_argument("--no-flash", action="store_true", help="batch: test only, don't flash")
    ap.add_argument("--auto", action="store_true",
                    help="skip the checks that need a human (LED look, BOOT/RESET press)")
    ap.add_argument("--app", help="after a PASS, flash this .bin (your real firmware)")
    ap.add_argument("--app-offset", default="0x0",
                    help="offset for --app (0x0 for a merged image, 0x10000 for an app-only bin)")
    ap.add_argument("--min-rssi", type=int, default=-85, help="Wi-Fi pass threshold, dBm")
    ap.add_argument("--skip-uart-pins", action="store_true",
                    help="leave IO16/IO17 (TX/RX) out of the short test")
    ap.add_argument("--csv", default=os.path.join(HERE, "results.csv"))
    ap.add_argument("--note", help="text stored in the notes column (e.g. batch/lot)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    try:
        {"batch": cmd_batch, "test": cmd_test, "info": cmd_info,
         "flash": cmd_flash, "monitor": cmd_monitor}[args.command](args)
    except KeyboardInterrupt:
        print("\nbye")

if __name__ == "__main__":
    main()
