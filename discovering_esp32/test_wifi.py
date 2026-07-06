import network
import time
from secrets import WIFI_SSID, WIFI_PASSWORD

# =========================================================================
# Remplace ces deux valeurs par tes identifiants WiFi.
# Note : l'ESP32 ne gere QUE le 2.4 GHz, pas le 5 GHz.
# Si ta box a deux reseaux, prends le 2.4 GHz.
# =========================================================================



def connecter_wifi(timeout_s=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Deja connecte :", wlan.ifconfig()[0])
        return wlan

    print("Connexion a '{}'...".format(WIFI_SSID))
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    t0 = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
            print("ECHEC : timeout apres {}s.".format(timeout_s))
            print("Verifie SSID/mot de passe et que le reseau est en 2.4 GHz.")
            return None
        print(".", end="")
        time.sleep(0.5)

    ip, masque, passerelle, dns = wlan.ifconfig()
    print("\nConnecte !")
    print("  IP        :", ip)
    print("  Passerelle:", passerelle)
    print("  DNS       :", dns)
    return wlan


connecter_wifi()