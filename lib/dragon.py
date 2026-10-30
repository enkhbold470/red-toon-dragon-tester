"""Red Eyes Toon Dragon board support for MicroPython (ESP32-C6-MINI-1U).

    import dragon
    dragon.eyes.color("red")            # both eyes
    dragon.eyes.color((0, 80, 255), 1)  # right eye only
    dragon.eyes.rainbow()
    if dragon.button():                 # BOOT button held?
        ...
    i2c = dragon.i2c()                  # Qwiic port
    ip = dragon.wifi("ssid", "password")

Facing the front of the board (USB-C at the bottom): eye 0 = D1 = left, eye 1 = D2 = right.
Pin numbers and the hardware rules behind them are in board/board.json.
"""
import time
from machine import Pin

__version__ = "1.0.0"

# ---- pins (GPIO numbers) -------------------------------------------------------
EYES = 8          # 2x SK6812 RGB, D1 -> D2 chain. Strapping pin: keep it free at boot.
BOOT = 9          # BOOT button SW2, active low, 10k pull-up. Strapping pin.
SDA = 0           # Qwiic J2 + J3.8. NO pull-ups on the board.
SCL = 14          # Qwiic J2 + J3.9
TX = 16           # UART0, J4.8
RX = 17           # UART0, J4.7
USB_DM, USB_DP = 12, 13   # native USB (the REPL). Don't touch.

# header pin -> GPIO (None = power)
J3 = {1: 7, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2, 7: 1, 8: 0, 9: 14}
J4 = {1: 23, 2: 22, 3: 21, 4: 20, 5: 19, 6: 18, 7: 17, 8: 16, 9: None, 10: None, 11: None}
J4_POWER = {9: "3V3", 10: "GND", 11: "5V"}

# Free GPIOs on the headers you can use for anything (ADC-capable: 0-6)
FREE = (1, 2, 3, 4, 5, 6, 7, 18, 19, 20, 21, 22, 23)
ADC_PINS = (0, 1, 2, 3, 4, 5, 6)

COLORS = {
    "off": (0, 0, 0), "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "yellow": (255, 160, 0), "orange": (255, 60, 0),
    "purple": (160, 0, 255), "pink": (255, 40, 120), "cyan": (0, 255, 200),
}


class Eyes:
    """The two RGB eyes. Colors are (r, g, b) 0-255 or a name from COLORS."""

    def __init__(self, brightness=0.25):
        self.brightness = brightness
        self._np = None
        self._state = [(0, 0, 0), (0, 0, 0)]

    @property
    def np(self):
        if self._np is None:   # created on first use so importing never drives GPIO8
            import neopixel
            self._np = neopixel.NeoPixel(Pin(EYES, Pin.OUT), 2)
        return self._np

    def _scale(self, c):
        if isinstance(c, str):
            c = COLORS[c]
        b = self.brightness
        return (int(c[0] * b), int(c[1] * b), int(c[2] * b))

    def color(self, c, eye=None):
        """Set both eyes, or one eye (0 = left, 1 = right)."""
        for i in ((0, 1) if eye is None else (eye,)):
            self._state[i] = c
            self.np[i] = self._scale(c)
        self.np.write()

    def off(self):
        self.color((0, 0, 0))

    def blink(self, c="red", times=3, ms=150):
        for _ in range(times):
            self.color(c)
            time.sleep_ms(ms)
            self.off()
            time.sleep_ms(ms)

    def rainbow(self, loops=1, ms=8):
        for _ in range(loops):
            for p in range(256):
                self.color(wheel(p), 0)
                self.color(wheel((p + 128) & 255), 1)
                time.sleep_ms(ms)

    def breathe(self, c="red", ms=1500):
        steps = 50
        base = COLORS[c] if isinstance(c, str) else c
        for i in list(range(steps)) + list(range(steps, -1, -1)):
            k = i / steps
            self.color((int(base[0] * k), int(base[1] * k), int(base[2] * k)))
            time.sleep_ms(ms // (2 * steps))


def wheel(pos):
    """0-255 -> rainbow color."""
    pos &= 255
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


eyes = Eyes()
_boot = Pin(BOOT, Pin.IN, Pin.PULL_UP)


def button():
    """True while the BOOT button is held."""
    return _boot.value() == 0


def wait_button(timeout_ms=None):
    """Block until BOOT is pressed and released. Returns False on timeout."""
    t0 = time.ticks_ms()
    while not button():
        if timeout_ms is not None and time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            return False
        time.sleep_ms(10)
    while button():
        time.sleep_ms(10)
    return True


def on_button(handler):
    """Call handler(pin) on each BOOT press (interrupt, debounce it yourself if needed)."""
    _boot.irq(trigger=Pin.IRQ_FALLING, handler=handler)


def i2c(freq=400_000):
    """I2C on the Qwiic port. The board has no pull-ups: your Qwiic module must have them."""
    from machine import I2C
    return I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=freq)


def uart(baud=115_200):
    """UART1 on the TX/RX header pins (the REPL is on USB, so these are free)."""
    from machine import UART
    return UART(1, baud, tx=TX, rx=RX)


def wifi(ssid, password, timeout_s=15):
    """Connect to Wi-Fi and return the IP. The -1U module needs an antenna on U.FL."""
    import network
    w = network.WLAN(network.STA_IF)
    w.active(True)
    if not w.isconnected():
        w.connect(ssid, password)
        t0 = time.ticks_ms()
        while not w.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                raise OSError("Wi-Fi connect timed out (antenna plugged in? right password?)")
            time.sleep_ms(200)
    return w.ifconfig()[0]


def temperature():
    """Chip die temperature in C (not room temperature)."""
    import esp32
    return esp32.mcu_temperature()


def info():
    import machine, os
    print("Red Eyes Toon Dragon | dragon.py", __version__, "|", os.uname().machine,
          "| MicroPython", os.uname().release, "| uid",
          ":".join("%02x" % b for b in machine.unique_id()))
