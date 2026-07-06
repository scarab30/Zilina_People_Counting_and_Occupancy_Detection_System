import network
import time
import json
from machine import I2C, Pin
from umqtt.simple import MQTTClient

from vl53l5cx.mp import VL53L5CXMP
from vl53l5cx import DATA_DISTANCE_MM, DATA_TARGET_STATUS
from vl53l5cx import RESOLUTION_8X8

from secrets import WIFI_SSID, WIFI_PASSWORD, MQTT_BROKER, MQTT_PORT

# =========================================================================
# CONFIG
# =========================================================================
CLIENT_ID = "xiao-esp32-tof"
SENSOR_ID = "capteur-porte-1"      # identifiant logique de ce capteur
TOPIC = b"tof/capteur-porte-1/matrice"

SDA_PIN = 5
SCL_PIN = 6
I2C_FREQ = 400_000
RANGING_FREQ = 10   # Hz (max 15 en 8x8)
COLS = 8


def connecter_wifi(timeout_s=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("WiFi : connexion a '{}'...".format(WIFI_SSID))
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                raise RuntimeError("WiFi : timeout")
            time.sleep(0.5)
    print("WiFi OK :", wlan.ifconfig()[0])
    return wlan


def connecter_mqtt():
    print("MQTT : connexion a {}:{}...".format(MQTT_BROKER, MQTT_PORT))
    client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, keepalive=30)
    client.connect()
    print("MQTT OK")
    return client


def make_sensor():
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    tof = VL53L5CXMP(i2c)
    if not tof.is_alive():
        raise ValueError("VL53L5CX non detecte")
    tof.init()
    tof.resolution = RESOLUTION_8X8
    tof.ranging_freq = RANGING_FREQ
    return tof


def main():
    connecter_wifi()
    client = connecter_mqtt()
    tof = make_sensor()
    tof.start_ranging({DATA_DISTANCE_MM, DATA_TARGET_STATUS})

    print("Publication des matrices sur '{}'. Ctrl+C pour arreter.".format(
        TOPIC.decode()))

    try:
        while True:
            if tof.check_data_ready():
                results = tof.get_ranging_data()

                # On envoie les listes brutes : le serveur interprete.
                # distance = 64 valeurs (mm), status = 64 valeurs (validite).
                # Le serveur ne garde que les zones ou status == 5 (STATUS_VALID).
                payload = {
                    "sensor": SENSOR_ID,
                    "t": time.ticks_ms(),      # horodatage local ESP (ms)
                    "cols": COLS,              # resolution (8 => grille 8x8)
                    "distance": list(results.distance_mm),
                    "status": list(results.target_status),
                }

                client.publish(TOPIC, json.dumps(payload))

            time.sleep(0.01)
    finally:
        tof.stop_ranging()
        client.disconnect()
        print("Arrete proprement")


main()