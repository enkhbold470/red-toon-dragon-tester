# AGENTS.md: building on the Red Eyes Toon Dragon

You are working on code for a real ESP32-C6 board that is plugged in over USB-C.
You can flash it, run code on it and read its output yourself, so check your work
on the hardware rather than guessing.

## The board in one paragraph

ESP32-C6-MINI-1U (RISC-V 160 MHz, Wi-Fi 6, BLE 5, Thread/Zigbee, 4 MB flash, no PSRAM,
**external U.FL antenna only**). It has two SK6812 RGB "eyes" on **GPIO8** (eye 0 = left,
eye 1 = right) and a **BOOT button on GPIO9** (active low). A Qwiic port has
**SDA=GPIO0 / SCL=GPIO14 with no pull-ups**. Two headers carry 13 free GPIOs plus
UART TX16/RX17, 3V3, GND and 5V. Power comes from USB-C. The full pin map, power tree,
part list and netlist are in [`board/board.json`](board/board.json). Read that file
instead of guessing pins.

## Loop: edit → run → read output

```bash
source .venv/bin/activate                  # set up once, see README
python dev.py run path/to/file.py          # uploads lib/dragon.py, runs the file, streams its prints
python dev.py exec "print(dragon.button())" # one-liner on the board (dragon is pre-imported)
python dev.py deploy path/to/file.py       # install as main.py: runs at every power-up
python dev.py undeploy                     # remove main.py (do this before handing the board back)
python -m unittest discover tests          # host checks: pins in json/lib/header agree, files compile
```

- `dev.py run` blocks until the program ends. For a program with a `while True` loop,
  run it in the background with a timeout and stop it. Stopping `dev.py` frees the
  port on macOS/Linux.
- If the board is not found: `python dev.py setup` flashes MicroPython and the library.
  `python tester/dragon_tester.py info` shows whether the chip answers at all.
- Something odd with the hardware? `python dev.py doctor` runs the full self-test.
  It needs a person to look at the LEDs and press buttons.

## Writing code for it

- MicroPython 1.29 (`ESP32_GENERIC_C6`). Use `import dragon` from `lib/dragon.py`:
  `dragon.eyes.color("red" | (r,g,b), eye=None|0|1)`, `eyes.blink/rainbow/breathe/off`,
  `dragon.button()`, `dragon.wait_button()`, `dragon.on_button(fn)`, `dragon.i2c()`,
  `dragon.uart()`, `dragon.wifi(ssid, pw) -> ip`, `dragon.temperature()`, `dragon.wheel(n)`.
- Start from the matching file in `examples/` (eyes, button, Wi-Fi web server, Qwiic,
  temperature, BLE).
- Wi-Fi credentials go on the board with `python dev.py secrets SSID PASSWORD`, then
  `from secrets import WIFI_SSID, WIFI_PASSWORD`. Never commit them.
- Arduino / ESP-IDF instead: `include/toon_dragon.h` has the same pin map. Use the
  "ESP32C6 Dev Module" board with USB CDC On Boot enabled.

## Hardware rules (breaking these damages the board or bricks the boot)

1. GPIO is 3.3 V only. Never connect 5 V to an IO pin.
2. GPIO8 and GPIO9 are strapping pins. Nothing external may hold them low during reset.
3. Never reconfigure GPIO12/13. They are the USB link, so you would lose the REPL and
   the flasher.
4. The 3V3 regulator gives 600 mA in total, and Wi-Fi peaks around 350 mA. Power large
   loads from 5V (J4.11) instead.
5. Wi-Fi and BLE need the U.FL antenna. Without it the range is only a few metres.
   That's not a code bug.
6. The eyes are bright: `dragon.eyes.brightness` defaults to 0.25. Keep it there for
   anything left on.

## Repo map

| path | what |
|---|---|
| `lib/dragon.py` | board library (runs on the board) |
| `examples/` | small runnable programs, one feature each |
| `board/board.json` | machine-readable hardware truth (pins, rules, parts, nets) |
| `include/toon_dragon.h` | C pin map for Arduino / ESP-IDF |
| `dev.py` | developer CLI (wraps mpremote + esptool) |
| `tester/` | factory flash + test station (CLI and web GUI) for batches of boards |
| `tests/` | host-side consistency checks (CI runs these) |

When you change a pin or a hardware fact, update `board/board.json`, `lib/dragon.py`
and `include/toon_dragon.h` together. `tests/` fails if they disagree.

## Done means

- `python -m unittest discover tests` passes.
- New code ran on the real board through `dev.py run`, and you read its output.
- Any new example has a header comment that says what it does and how to stop it.
- The board is left without a stray `main.py`, unless deploying was the task.
