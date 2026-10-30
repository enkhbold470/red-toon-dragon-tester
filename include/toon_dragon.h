// Red Eyes Toon Dragon pin map for Arduino-ESP32 and ESP-IDF (ESP32-C6-MINI-1U).
// Arduino IDE: board "ESP32C6 Dev Module", USB CDC On Boot: Enabled.
// Same data as board/board.json - keep them in sync (tests/test_repo.py checks).
#pragma once

#define DRAGON_EYES_PIN     8   // 2x SK6812 (GRB), D1 left -> D2 right. Strapping pin, keep high at boot.
#define DRAGON_EYES_COUNT   2
#define DRAGON_BOOT_PIN     9   // BOOT button, active low, 10k pull-up. Strapping pin.
#define DRAGON_SDA_PIN      0   // Qwiic J2 / J3.8 - no pull-ups on the board
#define DRAGON_SCL_PIN      14  // Qwiic J2 / J3.9
#define DRAGON_TX_PIN       16  // J4.8
#define DRAGON_RX_PIN       17  // J4.7

// Header J3 (left edge), pin 1..9
static const int DRAGON_J3[] = {7, 6, 5, 4, 3, 2, 1, 0, 14};
// Header J4 (right edge), pin 1..8 (J4.9 = 3V3, J4.10 = GND, J4.11 = 5V)
static const int DRAGON_J4[] = {23, 22, 21, 20, 19, 18, 17, 16};
