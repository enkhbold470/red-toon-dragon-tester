# Press BOOT to cycle eye colors. Ctrl-C to stop.
import dragon

colors = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "white", "off"]
i = 0
dragon.eyes.color(colors[i])
print("press BOOT to change color")
while True:
    dragon.wait_button()
    i = (i + 1) % len(colors)
    dragon.eyes.color(colors[i])
    print("eyes:", colors[i])
