# List what's plugged into the Qwiic port. The board has no I2C pull-ups:
# your Qwiic module must have them (almost all SparkFun/Adafruit ones do).
import dragon

found = dragon.i2c().scan()
print("Qwiic devices:", [hex(a) for a in found] or "none")
dragon.eyes.color("green" if found else "red")
