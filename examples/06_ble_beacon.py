# Advertise over Bluetooth LE as "ToonDragon" - find it with any BLE scanner app.
# Press BOOT to stop.
import bluetooth, struct
import dragon

NAME = b"ToonDragon"
adv = struct.pack("BBB", 2, 0x01, 0x06) + struct.pack("BB", len(NAME) + 1, 0x09) + NAME
ble = bluetooth.BLE()
ble.active(True)
ble.gap_advertise(100_000, adv_data=adv)
print("advertising as", NAME.decode(), "- press BOOT to stop")
dragon.eyes.breathe("blue")
dragon.wait_button()
ble.gap_advertise(None)
dragon.eyes.off()
