# Runs ON the Red Eyes Toon Dragon board (MicroPython), sent over the raw REPL
# by dragon_tester.py. Each test returns a dict; the host prints it as JSON.
import json, time, machine
from machine import Pin

LED_PIN = 8      # SK6812 x2 (D1 -> D2 chain), also a strapping pin (R7 pull-up)
BOOT_PIN = 9     # SW2 BOOT, R6 pull-up
SDA, SCL = 0, 14 # Qwiic J2 + header J3.8 / J3.9

# Header pins in physical order. 16/17 are UART0 TX/RX (J4.8 / J4.7).
J3 = [7, 6, 5, 4, 3, 2, 1, 0, 14]
J4 = [23, 22, 21, 20, 19, 18, 17, 16]


def t_chip():
    import esp, os
    u = machine.unique_id()
    r = {"uid": ":".join("%02x" % b for b in u),
         "freq_mhz": machine.freq() // 1000000,
         "flash_mb": esp.flash_size() // (1024 * 1024),
         "fw": os.uname().version}
    try:
        import esp32
        r["temp_c"] = esp32.mcu_temperature()
    except Exception:
        pass
    r["ok"] = r["flash_mb"] >= 4
    return r


def _read_all(pins, pull):
    out = {}
    for n in pins:
        out[n] = Pin(n, Pin.IN, pull).value()
    return out


def t_gpio(pins):
    """Find header pins stuck to GND / a rail, and solder bridges between pins.
    Uses only the chip's internal pulls, so nothing has to be plugged in."""
    stuck_low = [n for n, v in _read_all(pins, Pin.PULL_UP).items() if v != 1]
    stuck_high = [n for n, v in _read_all(pins, Pin.PULL_DOWN).items() if v != 0]
    bridges = []
    good = [n for n in pins if n not in stuck_low and n not in stuck_high]
    for drv in good:
        others = [n for n in good if n != drv]
        _read_all(others, Pin.PULL_UP)
        Pin(drv, Pin.OUT, value=0)
        time.sleep_us(200)
        for n in others:
            if Pin(n).value() == 0:
                pair = sorted((drv, n))
                if pair not in bridges:
                    bridges.append(pair)
        Pin(drv, Pin.IN, Pin.PULL_UP)
    for n in pins:
        Pin(n, Pin.IN)
    return {"stuck_low": stuck_low, "stuck_high": stuck_high, "bridges": bridges,
            "ok": not (stuck_low or stuck_high or bridges)}


def leds(r, g, b):
    import neopixel
    np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), 2)
    for i in range(2):
        np[i] = (r, g, b)
    np.write()


def t_leds_cycle():
    for c in ((60, 0, 0), (0, 60, 0), (0, 0, 60), (60, 60, 60)):
        leds(*c)
        time.sleep_ms(500)
    return {"ok": True}


def boot_state():
    return Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP).value()


def t_i2c():
    from machine import I2C
    i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=100000)
    found = ["0x%02x" % a for a in i2c.scan()]
    return {"found": found, "ok": True}


def t_wifi():
    import network
    w = network.WLAN(network.STA_IF)
    w.active(True)
    nets = w.scan()
    w.active(False)
    best = max([n[3] for n in nets] or [-127])
    return {"count": len(nets), "best_rssi": best, "ok": len(nets) > 0}


def run(name, *a):
    try:
        r = globals()["t_" + name](*a)
    except Exception as e:
        r = {"ok": False, "error": repr(e)}
    print("@@" + json.dumps(r))
