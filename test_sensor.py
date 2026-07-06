from machine import I2C, Pin
import time

from vl53l5cx.mp import VL53L5CXMP
from vl53l5cx import DATA_DISTANCE_MM, DATA_TARGET_STATUS
from vl53l5cx import STATUS_VALID, RESOLUTION_4X4

# Pins d'apres ton schema : SDA=5, SCL=6
# On demarre a 400kHz (plus tolerant qu'1MHz pour un premier test)
i2c = I2C(0, scl=Pin(6), sda=Pin(5), freq=400_000)

# Pas de LPN cable -> on cree le capteur sans
tof = VL53L5CXMP(i2c)

print("Reset du capteur...")
tof.reset()

if not tof.is_alive():
    raise ValueError("VL53L5CX non detecte")

print("Capteur detecte, upload du firmware (~84Ko, patiente)...")
tof.init()
print("Init OK")

tof.resolution = RESOLUTION_4X4
tof.ranging_freq = 2   # 2 Hz, tranquille pour debuter
grid = 3               # 4x4 -> retour a la ligne tous les 4 (index & 3)

tof.start_ranging({DATA_DISTANCE_MM, DATA_TARGET_STATUS})
print("Ranging demarre. Ctrl+C pour arreter.\n")

while True:
    if tof.check_data_ready():
        results = tof.get_ranging_data()
        distance = results.distance_mm
        status = results.target_status

        for i, d in enumerate(distance):
            if status[i] == STATUS_VALID:
                print("{:4}".format(d), end=" ")
            else:
                print("xxxx", end=" ")
            if (i & grid) == grid:
                print("")
        print("")
    time.sleep(0.05)