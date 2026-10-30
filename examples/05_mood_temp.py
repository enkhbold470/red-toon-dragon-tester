# Eyes follow the chip temperature: blue when cool, red when hot. Ctrl-C to stop.
import time
import dragon

while True:
    t = dragon.temperature()
    k = min(max((t - 25) / 25, 0), 1)          # 25 C -> blue, 50 C -> red
    dragon.eyes.color((int(255 * k), 0, int(255 * (1 - k))))
    print("chip %.1f C" % t)
    time.sleep(1)
