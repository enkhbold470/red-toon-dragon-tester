# Red Eyes Toon Dragon: flash & test station

A small Python tool that flashes and tests the **Red Eyes Toon Dragon** board
(ESP32-C6-MINI-1U, 2× SK6812 RGB eyes, USB-C, Qwiic). You plug a board in, the tool
flashes it and runs the tests, and the result is written to a CSV file. Then you plug
in the next board.

Board design: <https://heypcb.ai/p/961e9487c50d?view=pcb>

```
######## board #12 on /dev/cu.usbmodem1101 ########
== chip info
  PASS ESP32-C6  MAC 7c:0c:5f:ca:98:88  flash 4MB
== chip
  PASS 4 MB flash, 160 MHz, temp 29 C, v1.29.0 on 2026-08-24
== header GPIO shorts / solder bridges
  PASS 17 header pins clean (no shorts to GND/3V3, no bridges)
== LEDs (look at the board)
  ?  Did BOTH RGB eyes go red -> green -> blue -> white, and is the PWR LED on? [y/n/r] y
== BOOT button
  >> press and release BOOT (SW2) ...
  PASS BOOT button / GPIO9
== Wi-Fi radio + antenna
  PASS 6 networks, best RSSI -78 dBm (min -85)
== Qwiic / I2C (info only)
  .... devices on SDA=IO0/SCL=IO14: none
== RESET button
  >> press RESET (SW1) - the eyes should go dark ...
  PASS RESET button / EN

  BOARD #12: PASS
```

## Setup (once)

You need Python 3.9 or newer and a USB-C **data** cable.

```bash
git clone https://github.com/enkhbold470/red-toon-dragon-tester
cd red-toon-dragon-tester
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The MicroPython test firmware (v1.29.0, ESP32_GENERIC_C6) downloads on the first run
and is checked against a pinned SHA-256.

Linux: add yourself to the `dialout` group (`sudo usermod -aG dialout $USER`, then log
out and back in) so you can open the serial port.

## Testing a batch of boards

```bash
python dragon_tester.py
```

1. Plug in a board. The tool finds it on USB by itself (Espressif VID `303A`).
2. It flashes the board (about 9 s), then runs the tests. Two of them need you:
   - **look** at the LEDs and answer `y`, `n` or `r` (repeat the colour cycle)
   - **press** BOOT, then RESET, when the tool asks
3. A green **PASS** or red **FAIL** banner shows. Unplug the board and plug in the next one.

Each board takes about 30 s. Every board gets a row in `results.csv` (board number,
MAC, a pass/FAIL column per test, Wi-Fi RSSI) and a full log in `logs/<mac>.log`.
Boards are numbered in order. Write the number on the board with a marker.

Useful flags:

| flag | what it does |
|---|---|
| `--note "lot A"` | text saved in the notes column |
| `--auto` | skip the steps that need a person (LEDs, buttons). For a quick check. |
| `--app my_fw.bin` | after a board passes, flash your real firmware (merged image at `0x0`, or use `--app-offset 0x10000` for an app-only bin) |
| `--no-flash` | test boards that already run MicroPython |
| `--min-rssi -80` | make the Wi-Fi/antenna test stricter |
| `--port COM5` | use this port instead of finding one |
| `--skip-uart-pins` | leave IO16/IO17 out of the short test (if something is wired to them) |

## Debugging one board

```bash
python dragon_tester.py info      # can the PC see the chip? MAC, flash size
python dragon_tester.py flash     # put MicroPython on it
python dragon_tester.py test      # run every test, no flashing
python dragon_tester.py monitor   # serial console (Ctrl-] quits)
```

When a test fails, the tool prints which parts to check. All of those hints are
below too.

| symptom | where to look |
|---|---|
| **No port shows up / `info` fails** | Try a different USB-C cable (some only charge). Check that the PWR LED is on. If it's dark, check F1 (500 mA polyfuse), D4 (Schottky diode), U2 (AP2112K 3.3 V regulator). If it's lit, check the J1 USB-C D+/D− joints and U3 (USBLC6). Last resort: hold **BOOT**, tap **RESET**, let go of BOOT, then run `info` again. |
| **Flash fails partway** | Use download mode as above. Look at U1's solder joints and the 3V3 decoupling (C13, C3). |
| **GPIO "shorted to GND / 3V3"** | Solder bridge from that header pin to a GND or power pin. J4.8 (TX/IO16) sits right next to J4.9 (3V3). |
| **GPIO "IOx bridged to IOy"** | Solder bridge between two header pins, or between U1 pads. The report names the header pins. |
| **Neither RGB eye lights** | D1's data line is GPIO8 (U1 pad 22, pulled up by R7). The LEDs run on 5 V, so check D4/F1 and C2/C4/C5. |
| **Left eye works, right one doesn't** | D1 DOUT → D2 DIN link (net `LED_DATA2`), or D2 itself. |
| **Colours wrong or flickery** | The SK6812s run at 5 V but get 3.3 V data. That's at the edge of their logic threshold, and a weak D1 joint shows up here first. |
| **PWR LED dark but the board works** | Solder jumper **JP1** must be bridged. Cut it on purpose to turn the PWR LED off. Then check D3 and R11. |
| **BOOT not detected** | SW2 → GPIO9, with R6 10 k pull-up. |
| **RESET not detected** | SW1 → EN, with R5 10 k pull-up and C10 1 µF. |
| **Wi-Fi sees no networks / weak RSSI** | This board uses the **-1U** module (U.FL connector, no PCB antenna). Plug in an antenna. |
| **Qwiic sensor not found** | SDA = GPIO0, SCL = GPIO14, 3V3 on J2. The board has **no I²C pull-ups**, so your sensor board must have them. |

## Pinout

| header pin | signal | | header pin | signal |
|---|---|---|---|---|
| J3.1 | IO7 | | J4.1 | IO23 |
| J3.2 | IO6 | | J4.2 | IO22 |
| J3.3 | IO5 | | J4.3 | IO21 |
| J3.4 | IO4 | | J4.4 | IO20 |
| J3.5 | IO3 | | J4.5 | IO19 |
| J3.6 | IO2 | | J4.6 | IO18 |
| J3.7 | IO1 | | J4.7 | RX0 / IO17 |
| J3.8 | SDA / IO0 | | J4.8 | TX0 / IO16 |
| J3.9 | SCL / IO14 | | J4.9 | 3V3 |
| | | | J4.10 | GND |
| | | | J4.11 | 5V |

Other pins: RGB eyes (SK6812 ×2) on **GPIO8**, BOOT button on **GPIO9**, native USB on
GPIO12/13. Qwiic J2: GND, 3V3, SDA (IO0), SCL (IO14).

## How the tests work

`dragon_tester.py` runs on the PC. It flashes with `esptool` and then drives
MicroPython over its raw REPL. `board_side.py` holds the tests that run on the chip.

- **chip**: flash size ≥ 4 MB, CPU clock, die temperature, firmware version.
- **GPIO**: no extra hardware needed. Every header pin is read with the internal
  pull-up (a pin stuck at 0 is shorted to GND) and with the pull-down (a pin stuck at 1
  is shorted to a rail). Then each pin in turn is driven low while the others are
  pulled up. Any pin that follows it is bridged to it.
- **LEDs**: cycles both SK6812s through R, G, B and white, and you confirm.
- **BOOT**: watches GPIO9 go low, then high again.
- **RESET**: saves a marker in RAM, you press RESET, and the test checks the marker is
  gone (meaning the chip really restarted).
- **Wi-Fi**: scans for networks. It passes if one is seen above `--min-rssi`, which shows
  the radio and the antenna path work.
- **I²C**: scans the Qwiic bus. Info only, it can't fail.

To add a test, write `t_mytest()` in `board_side.py` that returns `{"ok": ..., ...}`,
then call `b.run("mytest")` from `run_tests()` in `dragon_tester.py`.

## License

MIT
