from machine import I2C, Pin
import time

from vl53l5cx.mp import VL53L5CXMP
from vl53l5cx import DATA_DISTANCE_MM, DATA_TARGET_STATUS
from vl53l5cx import STATUS_VALID, RESOLUTION_8X8

# =========================================================================
# CONFIG - modifie ces valeurs pour ajuster le comportement
# =========================================================================

# --- Sensibilite ---
# Un objet est "detecte" dans une zone quand sa distance descend sous
# SEUIL_RATIO * distance_de_repos. Plus la valeur est BASSE, plus il faut
# s'approcher pres du capteur pour declencher (moins sensible).
SEUIL_RATIO = 0.70

# --- Calibration ---
CALIB_FRAMES = 20

# --- Detection ---
TIMEOUT_PASSAGE_MS = 1500

# --- Affichage ---
AFFICHER_MATRICE = True   # False pour couper l'affichage grille
EFFACER_ECRAN = True      # False si le terminal affiche des caracteres bizarres

# --- Materiel ---
SDA_PIN = 5
SCL_PIN = 6
I2C_FREQ = 400_000
# ATTENTION : en 8x8 le capteur plafonne a 15 Hz. Ne pas depasser 15.
RANGING_FREQ = 10   # Hz

# =========================================================================
# ZONES  (grille 8x8, index 0..63, lus ligne par ligne)
#   0  1  2  3  4  5  6  7
#   8 ...                15
#  ...
#  56 57 58 59 60 61 62 63
# Zone A = 4 colonnes de gauche, Zone B = 4 colonnes de droite.
# =========================================================================
COLS = 8
ZONE_A = [i for i in range(64) if (i % COLS) < 4]
ZONE_B = [i for i in range(64) if (i % COLS) >= 4]


def make_sensor():
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    tof = VL53L5CXMP(i2c)
    if not tof.is_alive():
        raise ValueError("VL53L5CX non detecte")
    tof.init()
    tof.resolution = RESOLUTION_8X8
    tof.ranging_freq = RANGING_FREQ
    return tof


def mediane_zone(distance, status, indices):
    """Distance mediane des zones valides parmi 'indices', ou None."""
    vals = [distance[i] for i in indices if status[i] == STATUS_VALID]
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def afficher_matrice(distance, status, count=None):
    """Affiche la grille de distances (mm). 'xxxx' = zone sans mesure valide."""
    lignes = []
    for row in range(COLS):
        cases = []
        for col in range(COLS):
            i = row * COLS + col
            if status[i] == STATUS_VALID:
                cases.append("{:4}".format(distance[i]))
            else:
                cases.append("xxxx")
        lignes.append(" ".join(cases))

    if EFFACER_ECRAN:
        print("\x1b[2J\x1b[H", end="")
    print("\n".join(lignes))
    if count is not None:
        print("\ncount = {}".format(count))


def calibrer(tof):
    """Mesure la distance de repos (sol/fond) pour chaque zone."""
    print("Calibration... ne rien mettre sous le capteur.")
    somme_a, somme_b, n = 0, 0, 0
    while n < CALIB_FRAMES:
        if tof.check_data_ready():
            results = tof.get_ranging_data()
            da = mediane_zone(results.distance_mm, results.target_status, ZONE_A)
            db = mediane_zone(results.distance_mm, results.target_status, ZONE_B)
            if da is not None and db is not None:
                somme_a += da
                somme_b += db
                n += 1
        time.sleep(0.02)
    repos_a = somme_a / CALIB_FRAMES
    repos_b = somme_b / CALIB_FRAMES
    seuil_a = repos_a * SEUIL_RATIO
    seuil_b = repos_b * SEUIL_RATIO
    print("Repos A={:.0f}mm B={:.0f}mm | seuils A<{:.0f} B<{:.0f}".format(
        repos_a, repos_b, seuil_a, seuil_b))
    return seuil_a, seuil_b


def on_passage(sens, count):
    """Appelee a chaque passage detecte. C'est ICI que tu brancheras
    plus tard le MQTT/HTTP."""
    print(">>> {} | count = {}".format(sens, count))


def main():
    tof = make_sensor()
    tof.start_ranging({DATA_DISTANCE_MM, DATA_TARGET_STATUS})

    seuil_a, seuil_b = calibrer(tof)

    count = 0
    premiere = None   # None | "A" | "B"
    t_premiere = 0

    print("Comptage demarre (8x8). Ctrl+C pour arreter.\n")
    time.sleep(1)

    while True:
        if tof.check_data_ready():
            # --- UNE seule lecture du capteur par frame ---
            results = tof.get_ranging_data()
            distance = results.distance_mm
            status = results.target_status

            # Affichage (utilise les memes donnees)
            if AFFICHER_MATRICE:
                afficher_matrice(distance, status, count)

            # Detection (utilise les memes donnees)
            da = mediane_zone(distance, status, ZONE_A)
            db = mediane_zone(distance, status, ZONE_B)
            now = time.ticks_ms()

            a_active = da is not None and da < seuil_a
            b_active = db is not None and db < seuil_b

            if premiere is not None:
                if time.ticks_diff(now, t_premiere) > TIMEOUT_PASSAGE_MS:
                    premiere = None

            if premiere is None:
                if a_active and not b_active:
                    premiere = "A"
                    t_premiere = now
                elif b_active and not a_active:
                    premiere = "B"
                    t_premiere = now

            elif premiere == "A":
                if b_active:
                    count += 1
                    on_passage("ENTREE", count)
                    premiere = None
                elif not a_active:
                    premiere = None

            elif premiere == "B":
                if a_active:
                    count -= 1
                    on_passage("SORTIE", count)
                    premiere = None
                elif not b_active:
                    premiere = None

        time.sleep(0.01)


main()