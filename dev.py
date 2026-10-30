#!/usr/bin/env python3
"""Develop on the Red Eyes Toon Dragon board.

    python dev.py setup                 # flash MicroPython + install the dragon library (once per board)
    python dev.py run examples/01_hello_eyes.py   # run a file now, see its output (Ctrl-C stops it)
    python dev.py deploy my_app.py      # make it the app that starts at power-up (main.py)
    python dev.py undeploy              # remove main.py again
    python dev.py exec "dragon.eyes.color('purple')"
    python dev.py repl                  # interactive MicroPython prompt (Ctrl-] quits)
    python dev.py secrets SSID PASSWORD # store Wi-Fi credentials on the board (never in git)
    python dev.py ls | reset | info
    python dev.py doctor                # full hardware self-test (LEDs, buttons, shorts, Wi-Fi)

Every command finds the board by itself; pass --port to pick one.
"""
import argparse, os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tester"))
import dragon_tester as dt  # noqa: E402

LIB = os.path.join(ROOT, "lib", "dragon.py")


def port_of(args):
    port = args.port or dt.wait_for_port(3)
    if not port:
        sys.exit("No board found on USB. " + dt.HINTS["usb"])
    return port


def mpremote(port, *cmd):
    """Run mpremote commands ("a", "b", "+", "c", ...) against the board."""
    full = [sys.executable, "-m", "mpremote", "connect", port, *cmd]
    if os.name == "posix":   # become mpremote, so stopping dev.py also frees the port
        sys.stdout.flush()
        os.execv(sys.executable, full)
    try:
        return subprocess.call(full)
    except KeyboardInterrupt:
        return 130


INSTALL = ["cp", os.path.relpath(LIB), ":dragon.py", "+"]   # prefix: refresh the library on the board


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["setup", "install", "run", "deploy", "undeploy", "exec",
                                        "repl", "secrets", "ls", "reset", "info", "doctor"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--port")
    a = ap.parse_args()
    cmd = a.command

    if cmd == "doctor":
        sys.exit(subprocess.call([sys.executable, os.path.join(ROOT, "tester", "dragon_tester.py"),
                                  "test", "--csv", os.path.join(ROOT, "tester", "doctor.csv")]
                                 + (["--port", a.port] if a.port else [])))
    if cmd in ("run", "deploy") and a.args and not os.path.isfile(a.args[0]):
        sys.exit(f"no such file: {a.args[0]}")
    port = port_of(a)

    if cmd == "setup":
        print(f"flashing MicroPython to {port} ...")
        good, out = dt.flash(port, dt.firmware_path())
        if not good:
            print(out[-1200:])
            sys.exit(dt.HINTS["flash"])
        port = dt.wait_for_port(15) or port
        rc = mpremote(port, *INSTALL, "exec", "import dragon; dragon.info(); dragon.eyes.blink('green')")
        print("ready - try: python dev.py run examples/01_hello_eyes.py" if rc == 0 else "install failed")
        sys.exit(rc)
    if cmd == "install":
        sys.exit(mpremote(port, *INSTALL[:-1]))
    if cmd == "run":
        if not a.args:
            sys.exit("usage: dev.py run FILE.py")
        sys.exit(mpremote(port, *INSTALL, "run", a.args[0]))
    if cmd == "deploy":
        if not a.args:
            sys.exit("usage: dev.py deploy FILE.py")
        sys.exit(mpremote(port, *INSTALL, "cp", a.args[0], ":main.py", "+", "reset"))
    if cmd == "undeploy":
        sys.exit(mpremote(port, "rm", ":main.py", "+", "reset"))
    if cmd == "exec":
        sys.exit(mpremote(port, "exec", "import dragon\n" + " ".join(a.args)))
    if cmd == "repl":
        sys.exit(mpremote(port, "repl"))
    if cmd == "secrets":
        if len(a.args) != 2:
            sys.exit('usage: dev.py secrets "SSID" "PASSWORD"')
        code = (f"f=open('secrets.py','w');f.write('WIFI_SSID = %r\\nWIFI_PASSWORD = %r\\n'"
                f" % ({a.args[0]!r}, {a.args[1]!r}));f.close();print('saved secrets.py')")
        sys.exit(mpremote(port, "exec", code))
    if cmd == "ls":
        sys.exit(mpremote(port, "ls"))
    if cmd == "reset":
        sys.exit(mpremote(port, "reset"))
    if cmd == "info":
        sys.exit(mpremote(port, *INSTALL, "exec", "import dragon; dragon.info()"))


if __name__ == "__main__":
    main()
