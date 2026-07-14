import json
import sqlite3
import threading
import asyncio
import time
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# =========================================================================
# CONFIG
# =========================================================================
BROKER = "localhost"
PORT = 1883
TOPIC = "tof/matrice/post"
DB_PATH = "passages.db"

COLS = 8
STATUS_VALID = 5

# --- Comptage (reglable ici, sans toucher l'ESP) ---
SEUIL_RATIO = 0.70        # sensibilite : plus bas = moins sensible
CALIB_FRAMES = 20         # frames moyennees pour la distance de repos
TIMEOUT_PASSAGE_S = 1.5   # delai max entre 1ere et 2eme zone

# =========================================================================
# LOGIQUE DE COMPTAGE (portee depuis l'ESP)
# =========================================================================
class Counter:
    def __init__(self, cols=COLS):
        self.cols = cols
        n = cols * cols
        half = cols // 2
        self.zone_a = [i for i in range(n) if (i % cols) < half]
        self.zone_b = [i for i in range(n) if (i % cols) >= half]
        # calibration
        self._calib_a, self._calib_b = [], []
        self.seuil_a = self.seuil_b = None
        self.calibrated = False
        # machine a etats
        self.premiere = None       # None | "A" | "B"
        self.t_premiere = 0.0
        self.count = 0
        self._recalib_requested = False

    def request_recalibration(self):
        """Appele par l'endpoint HTTP. Pose juste un drapeau ;
        le reset reel se fait dans le thread MQTT (process)."""
        self._recalib_requested = True

    def _reset_calibration(self):
        # Remet a zero la calibration (distance de repos), PAS le count.
        self._calib_a, self._calib_b = [], []
        self.seuil_a = self.seuil_b = None
        self.calibrated = False
        self.premiere = None
        print("Recalibration demandee...")

    def _mediane(self, distance, status, indices):
        vals = sorted(distance[i] for i in indices if status[i] == STATUS_VALID)
        if not vals:
            return None
        return vals[len(vals) // 2]

    def process(self, payload):
        """Traite une frame. Retourne 'ENTREE', 'SORTIE' ou None."""
        if self._recalib_requested:
            self._recalib_requested = False
            self._reset_calibration()

        distance = payload["distance"]
        status = payload["status"]
        da = self._mediane(distance, status, self.zone_a)
        db = self._mediane(distance, status, self.zone_b)

        # --- Phase de calibration ---
        if not self.calibrated:
            if da is not None and db is not None:
                self._calib_a.append(da)
                self._calib_b.append(db)
                if len(self._calib_a) >= CALIB_FRAMES:
                    repos_a = sum(self._calib_a) / len(self._calib_a)
                    repos_b = sum(self._calib_b) / len(self._calib_b)
                    self.seuil_a = repos_a * SEUIL_RATIO
                    self.seuil_b = repos_b * SEUIL_RATIO
                    self.calibrated = True
                    print("Calibre : seuils A<{:.0f} B<{:.0f}".format(
                        self.seuil_a, self.seuil_b))
            return None

        # --- Detection ---
        now = time.monotonic()
        a_active = da is not None and da < self.seuil_a
        b_active = db is not None and db < self.seuil_b

        if self.premiere is not None and (now - self.t_premiere) > TIMEOUT_PASSAGE_S:
            self.premiere = None

        evt = None
        if self.premiere is None:
            if a_active and not b_active:
                self.premiere, self.t_premiere = "A", now
            elif b_active and not a_active:
                self.premiere, self.t_premiere = "B", now
        elif self.premiere == "A":
            if b_active:
                self.count += 1
                evt, self.premiere = "ENTREE", None
            elif not a_active:
                self.premiere = None
        elif self.premiere == "B":
            if a_active:
                self.count -= 1
                evt, self.premiere = "SORTIE", None
            elif not b_active:
                self.premiere = None
        return evt


# =========================================================================
# ETAT PARTAGE (thread MQTT ecrit, WebSocket lit)
# =========================================================================
_lock = threading.Lock()
_latest_frame = None
_count = 0
_calibrated = False

counter = Counter()


# =========================================================================
# BASE DE DONNEES : uniquement les passages
# =========================================================================
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS passages (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            moment  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sensor  TEXT,
            room    TEXT,
            sens    TEXT,      -- ENTREE / SORTIE
            count   INTEGER    -- count courant apres ce passage
        )
    """)
    con.commit()
    con.close()


def enregistrer_passage(sensor, room, sens, count):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO passages (sensor, room, sens, count) VALUES (?, ?, ?, ?)",
        (sensor, room, sens, count),
    )
    con.commit()
    con.close()


# =========================================================================
# MQTT
# =========================================================================
def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connecte, abonnement a", TOPIC)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global _latest_frame, _count, _calibrated
    try:
        payload = json.loads(msg.payload)
    except (ValueError, TypeError):
        return

    evt = counter.process(payload)   # logique de comptage

    with _lock:
        _latest_frame = payload
        _count = counter.count
        _calibrated = counter.calibrated

    if evt is not None:
        enregistrer_passage(
            payload.get("sensor"), payload.get("room"), evt, counter.count
        )
        print("{} | count = {}".format(evt, counter.count))


def demarrer_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    return client


# =========================================================================
# FASTAPI
# =========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    client = demarrer_mqtt()
    yield
    client.loop_stop()
    client.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/recalibrate")
async def recalibrate():
    counter.request_recalibration()
    return {"ok": True}


# --- Historique ---
def _query(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.get("/history", response_class=HTMLResponse)
async def history_page():
    with open("history.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/stats")
async def api_stats():
    rows = _query("SELECT sens, COUNT(*) AS n FROM passages GROUP BY sens")
    stats = {r["sens"]: r["n"] for r in rows}
    last = _query("SELECT count FROM passages ORDER BY id DESC LIMIT 1")
    return {
        "entrees": stats.get("ENTREE", 0),
        "sorties": stats.get("SORTIE", 0),
        "occupation": last[0]["count"] if last else 0,
    }


@app.get("/api/timeseries")
async def api_timeseries():
    # Occupation dans le temps : le champ count est deja le cumul apres passage
    return _query("SELECT moment, count FROM passages ORDER BY id")


@app.get("/api/hourly")
async def api_hourly():
    # Entrees / sorties agregees par heure (moment est en UTC)
    return _query("""
        SELECT strftime('%Y-%m-%d %H:00', moment) AS heure,
               SUM(CASE WHEN sens='ENTREE' THEN 1 ELSE 0 END) AS entrees,
               SUM(CASE WHEN sens='SORTIE' THEN 1 ELSE 0 END) AS sorties
        FROM passages
        GROUP BY heure
        ORDER BY heure
    """)


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            with _lock:
                frame = _latest_frame
                count = _count
                calibrated = _calibrated
            if frame is not None:
                msg = dict(frame)
                msg["count"] = count
                msg["calibrated"] = calibrated
                await websocket.send_json(msg)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)