# The dragon wakes up: blink, rainbow, then glow red.
import dragon

dragon.info()
dragon.eyes.blink("white", times=2)
dragon.eyes.rainbow(loops=2)
dragon.eyes.color("red")
print("eyes are red - try dragon.eyes.color('purple') in the REPL")
