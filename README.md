# Red Eyes Toon Dragon

Everything you need for the **Red Eyes Toon Dragon** board, an ESP32-C6 with two RGB
eyes, USB-C, Qwiic and two GPIO headers:

- **Build on it.** A MicroPython library, examples, and a one-command run/deploy loop.
  Works with you or your AI coding agent.
- **Test it.** A flash-and-test station for batches of boards, with a CLI and a web GUI.

Board design: <https://heypcb.ai/p/961e9487c50d?view=pcb>

## Quick start

You need Python 3.9+ and a USB-C **data** cable.

```bash
git clone https://github.com/enkhbold470/red-toon-dragon-tester
cd red-toon-dragon-tester
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python dev.py setup                          # once per board: MicroPython + dragon library
python dev.py run examples/01_hello_eyes.py  # the eyes light up
```

Linux: run `sudo usermod -aG dialout $USER` once, then log in again.

## Build on it

```python
import dragon

dragon.eyes.color("purple")          # both eyes
dragon.eyes.color((0, 80, 255), 1)   # right eye only (0 = left, 1 = right)
dragon.eyes.rainbow()
dragon.wait_button()                 # BOOT button
ip = dragon.wifi("ssid", "password")
sensors = dragon.i2c().scan()        # Qwiic port
```

| command | what it does |
|---|---|
| `python dev.py run app.py` | run a file now, see its output (Ctrl-C stops it) |
| `python dev.py deploy app.py` | make it start at every power-up |
| `python dev.py undeploy` | remove it again |
| `python dev.py exec "dragon.eyes.off()"` | run one line |
| `python dev.py repl` | interactive MicroPython prompt |
| `python dev.py secrets SSID PASSWORD` | store Wi-Fi credentials on the board, not in git |
| `python dev.py doctor` | full hardware self-test |

### Examples

| file | shows |
|---|---|
| `01_hello_eyes.py` | blink, rainbow, set a color |
| `02_button.py` | BOOT button cycles eye colors |
| `03_wifi_web.py` | color picker web page: change the eyes from your phone |
| `04_qwiic_scan.py` | find sensors on the Qwiic port |
| `05_mood_temp.py` | eyes follow the chip temperature |
| `06_ble_beacon.py` | Bluetooth LE advertising as "ToonDragon" |

### With an AI agent

The repo works with coding agents out of the box (Claude Code, Codex, Cursor and others):

- [`AGENTS.md`](AGENTS.md) (also read as `CLAUDE.md`) explains the edit → run on hardware
  → read output loop, the library API, the hardware rules an agent must not break, and
  what "done" means.
- [`board/board.json`](board/board.json) describes the hardware in machine-readable form:
  every pin, rail, rule and part, plus the full netlist from the KiCad design. Agents
  read it instead of guessing pins.
- `python -m unittest discover tests` checks that the pin maps in the JSON, the
  library and the C header agree. CI runs it on every push.

Just ask: *"make the eyes blink faster when the room gets hot"*. The agent can run the
result on the board and read the output itself.

### Arduino / ESP-IDF

Include [`include/toon_dragon.h`](include/toon_dragon.h) for the pin map. Choose
"ESP32C6 Dev Module" with **USB CDC On Boot: Enabled**. Drive the eyes with any
WS2812/NeoPixel library: 2 pixels, GRB, on `DRAGON_EYES_PIN`.

## Hardware

Facing the front, the module is at the top and USB-C at the bottom. The left eye is D1
and the right eye is D2. RESET is on the left, BOOT on the right.

| header pin | signal | | header pin | signal |
|---|---|---|---|---|
| J3.1 | IO7 | | J4.1 | IO23 |
| J3.2 | IO6 | | J4.2 | IO22 |
| J3.3 | IO5 | | J4.3 | IO21 |
| J3.4 | IO4 | | J4.4 | IO20 |
| J3.5 | IO3 | | J4.5 | IO19 |
| J3.6 | IO2 | | J4.6 | IO18 |
| J3.7 | IO1 | | J4.7 | RX / IO17 |
| J3.8 | SDA / IO0 | | J4.8 | TX / IO16 |
| J3.9 | SCL / IO14 | | J4.9 | 3V3 |
| | | | J4.10 | GND |
| | | | J4.11 | 5V |

- **Eyes:** 2× SK6812 on GPIO8. **BOOT:** GPIO9. **Qwiic J2:** GND, 3V3, SDA (IO0), SCL (IO14).
- ADC-capable pins: IO0 to IO6.
- 3.3 V logic only. The 3V3 regulator gives 600 mA in total. GPIO8 and GPIO9 are
  strapping pins.
- **Antenna:** this is the -1U module, with a U.FL connector and no PCB antenna. Without
  an antenna, Wi-Fi and BLE only reach a few metres.
- The Qwiic port has **no I²C pull-ups**. Use Qwiic modules that have their own (most do).

## Test station: flash and test many boards

```bash
python tester/dragon_web.py          # browser GUI, opens http://127.0.0.1:8765
python tester/dragon_tester.py       # same thing in the terminal
```

Press **Start testing** and plug in a board. It gets flashed and tested on its own,
and you answer the LED question with **Y/N** (on screen or on the keyboard) and press
BOOT and RESET when asked. Then a big **PASS** or **FAIL** shows. Unplug the board, plug
in the next one, and so on. Each board takes about 30 s. Every result goes to
`tester/results.csv` (board number, MAC, a pass/FAIL column per test, Wi-Fi RSSI) and
`tester/logs/<mac>.log`. The GUI keeps a live table with a yield count.

| test | how |
|---|---|
| chip | ESP32-C6 found, 4 MB flash, clock, die temperature |
| GPIO | every header pin checked for shorts to GND or 3V3 and bridges to its neighbours, using only the chip's internal pulls. No test jig needed. |
| LEDs | both eyes cycle R → G → B → white, and you confirm. The PWR LED is checked too. |
| BOOT | waits for GPIO9 to go low, then high again |
| RESET | the chip must really restart; crash or watchdog resets don't count |
| Wi-Fi | scan must see a network above `--min-rssi` (radio + antenna) |
| I²C | Qwiic bus scan (info only) |

Options (CLI flags; in the GUI the main ones are checkboxes): `--note "lot A"`,
`--auto` (skip the steps that need a person), `--no-flash`, `--min-rssi -70`,
`--app my_fw.bin` (flash your real firmware after a PASS, with `--app-offset 0x10000`
for app-only images), `--port`, `--skip-uart-pins`. Use
`python tester/dragon_web.py --listen 0.0.0.0:8765` to open the GUI from another
device on your network.

**Set `--min-rssi` for your room.** Test one board with an antenna and one without, and
pick a value between the two RSSI readings. Otherwise a board with no antenna can still
pass when it's close to the router.

## Troubleshooting

| symptom | where to look |
|---|---|
| **No port shows up** | Try a different USB-C cable (some only charge). PWR LED dark? Check F1 (polyfuse), D4 (Schottky), U2 (AP2112K 3.3 V). PWR LED on? Check the J1 D+/D− joints and U3 (USBLC6). Last resort: hold **BOOT**, tap **RESET**, let go of BOOT, then retry. |
| **Flash fails partway** | Use download mode as above. Check U1's solder joints and the 3V3 decoupling (C13, C3). |
| **GPIO shorted to GND / 3V3** | Solder bridge to a power pin. J4.8 (TX/IO16) sits right next to J4.9 (3V3). |
| **GPIO "IOx bridged to IOy"** | Solder bridge between two header pins, or between U1 pads. |
| **Neither eye lights** | Data is GPIO8 (U1 pad 22, R7 pull-up). The eyes run on 5 V, so check D4/F1 and C2/C4/C5. |
| **Left eye works, right one doesn't** | D1 DOUT → D2 DIN (net `LED_DATA2`), or D2 itself. |
| **Colours wrong or flickery** | 3.3 V data into 5 V SK6812s is at the edge of their logic threshold. A weak D1 joint shows up here first. |
| **PWR LED dark but the board works** | Solder jumper **JP1** on the back must be bridged. Then check D3 and R11. |
| **BOOT not detected** | SW2 → GPIO9, with R6 10 k pull-up. |
| **RESET not detected** | SW1 → EN, with R5 10 k + C10 1 µF. |
| **"chip restarted by itself"** | Crash or watchdog during the test. Check the 5V/3V3 rails and the USB cable. |
| **Wi-Fi sees nothing / weak RSSI** | Plug an antenna into the U.FL connector. |
| **Qwiic sensor not found** | Your module needs I²C pull-ups. Check the cable orientation. |

## Repo layout

```
lib/dragon.py          MicroPython board library
examples/              runnable examples
board/board.json       machine-readable hardware description
include/toon_dragon.h  C pin map (Arduino / ESP-IDF)
dev.py                 developer CLI
tester/                factory test station (CLI + web GUI)
tests/                 host-side checks
AGENTS.md              guide for AI coding agents
```

## License

MIT
