import json

import paho.mqtt.client as mqtt

# =========================================================================
# CONFIG
# =========================================================================
BROKER = "localhost"          # le serveur tourne sur la meme machine que le broker
PORT = 1883
TOPIC = "tof/matrice/post"    # doit correspondre au topic publie par l'ESP

COLS = 8
STATUS_VALID = 5              # valeur de status consideree comme mesure valide


def afficher_grille(payload):
    """Reaffiche la matrice recue, facon terminal. 'xxxx' = zone invalide."""
    distance = payload["distance"]
    status = payload["status"]
    cols = payload.get("cols", COLS)

    lignes = []
    for row in range(cols):
        cases = []
        for col in range(cols):
            i = row * cols + col
            if status[i] == STATUS_VALID:
                cases.append("{:4}".format(distance[i]))
            else:
                cases.append("xxxx")
        lignes.append(" ".join(cases))

    print("\x1b[2J\x1b[H", end="")   # efface l'ecran + curseur en haut
    print("sensor={}  t={}".format(payload.get("sensor"), payload.get("t")))
    print("\n".join(lignes))


# --- Callbacks paho-mqtt (API v2) ---

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connecte au broker. Abonnement a '{}'".format(TOPIC))
        client.subscribe(TOPIC)
    else:
        print("Echec connexion, code:", reason_code)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except (ValueError, TypeError) as e:
        print("Message non-JSON ignore:", e)
        return
    afficher_grille(payload)


def main():
    # API v2 de paho-mqtt (>= 2.0). Si tu es en 1.x, enleve le 1er argument.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print("Connexion a {}:{}...".format(BROKER, PORT))
    client.connect(BROKER, PORT, keepalive=60)

    # Boucle bloquante : ecoute les messages en continu. Ctrl+C pour arreter.
    client.loop_forever()


if __name__ == "__main__":
    main()