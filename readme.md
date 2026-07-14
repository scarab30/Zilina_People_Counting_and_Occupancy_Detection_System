# Žilinská univerzita v Žiline | People Counting and Occupancy Detection System Using the VL53L5CX ToF Sensor | Internship

**Authors:**
- Noah GALLOIS (FR)
- César CONSTANT (FR)

**Referees:**
- Lukáš Formanek
- Peter Šarafín

## Description of the project

The aim of this project is to design and implement a privacy-preserving system for people counting and occupancy detection in indoor spaces. The system is based on the ESP32-S3 microcontroller and the VL53L5CX time-of-flight sensor, which provides an 8×8 distance matrix for spatial depth measurement.

The system monitors a selected area, such as a doorway, corridor, or room entrance, and analyzes changes in the distance map to detect the presence and movement of people. By evaluating movement direction and object position over time, the system estimates entries and exits and determines the current occupancy of the monitored space.

Measured and processed data are displayed through a web interface, where users can view real-time occupancy status, a live heatmap, people-count statistics, and historical records. Detection parameters such as distance threshold and counting sensitivity are configurable server-side.

This system can be used in smart buildings, classrooms, offices, laboratories, meeting rooms, or public spaces where it is useful to monitor occupancy without using cameras.

## Architecture

The core design principle is **"dumb sensor, smart server"**: the ESP32 does as little as possible (it only streams raw sensor data), while all interpretation (calibration, counting, direction detection) happens server-side. This keeps the embedded code simple and lets us iterate on the algorithm without reflashing the board.

```
VL53L5CX --I2C--> ESP32-S3 --WiFi/MQTT--> Mosquitto broker --> FastAPI server --> Web UI
                  (raw 8x8 matrix,                              (counting logic,   (live heatmap,
                   JSON, ~10 Hz)                                 SQLite storage,    counter,
                                                                 WebSocket)         history)
```

Data flow:
1. The ESP32 reads the 8×8 matrix (64 distances + 64 status values) and publishes it as JSON over MQTT at ~10 Hz.
2. Mosquitto receives the stream.
3. The FastAPI server subscribes via paho-mqtt (background thread), runs the counting logic, persists passage events to SQLite, and pushes live data to the browser via WebSocket.
4. The web UI shows a live heatmap, the current count, and a history page with charts.

## Components & technologies used

**Hardware**
- Seeed Studio XIAO ESP32-S3
- VL53L5CX-SATEL sensor module (STMicroelectronics evaluation board)

**Embedded (on the board)**
- MicroPython (Seeed XIAO ESP32S3 build, from micropython.org)
- `vl53l5cx` MicroPython driver (from https://github.com/mp-extras/vl53l5cx)
- `umqtt.simple` (MQTT client)

**Tooling (PC)**
- `esptool` (flashing firmware)
- `mpremote` (file management + REPL over serial)
- Python 3.9+
- Visual Studio Code / PyCharm

**Server**
- FastAPI + uvicorn (web server, WebSocket)
- paho-mqtt (MQTT subscriber)
- Mosquitto (MQTT broker)
- SQLite (history storage)
- Chart.js (charts, loaded via CDN — no npm/Node.js needed)

## How to install

### 1. Flash MicroPython on the ESP32-S3

> **Important — flash offset:** the ESP32-**S3** must be flashed at address `0x0`, **not** `0x1000`. Flashing at the wrong offset makes the board boot-loop with `invalid header: 0xffffffff` and no working REPL. Always follow the official board page:
> https://micropython.org/download/SEEED_XIAO_ESP32S3/

Put the board in bootloader mode (hold **B/BOOT**, press/release **R/RESET**, release **B**), then:

```bash
esptool --chip esp32s3 --port COM6 erase-flash
esptool --chip esp32s3 --port COM6 write-flash 0x0 SEEED_XIAO_ESP32S3-<version>.bin
```

> **Note on the serial port:** the XIAO ESP32-S3 uses native USB, so its COM number changes when it re-enumerates (e.g. COM6 → COM4) after flashing or entering the bootloader. Always check the current port with `mpremote connect list` (the board is the line with the Espressif VID `303a:`).

### 2. Install the sensor library on the board

Clone the driver repo, then from inside the cloned folder:

```bash
git clone https://github.com/mp-extras/vl53l5cx.git
cd vl53l5cx

mpremote connect COM6 mkdir :lib
mpremote connect COM6 mkdir :lib/vl53l5cx
mpremote connect COM6 cp vl53l5cx/__init__.py :lib/vl53l5cx/__init__.py
mpremote connect COM6 cp vl53l5cx/_config_file.py :lib/vl53l5cx/_config_file.py
mpremote connect COM6 cp vl53l5cx/mp.py :lib/vl53l5cx/mp.py
mpremote connect COM6 cp vl53l5cx/vl_fw_config.bin :lib/vl53l5cx/vl_fw_config.bin
```

> `vl_fw_config.bin` (~84 KB) is the sensor firmware; it is uploaded to the sensor on every init, so it must be present on the board.

### 3. Install the MQTT client on the board

```bash
mpremote connect COM6 mip install umqtt.simple
```

### 4. Configure and deploy the ESP firmware

Create a `secrets.py` (WiFi + broker credentials) and deploy it, then deploy the main sensor script. `secrets.py` is git-ignored.

```bash
mpremote connect COM6 cp secrets.py :secrets.py
mpremote connect COM6 cp capteur_mqtt.py :main.py
```

`main.py` runs automatically on power-up. The board reads the matrix and publishes JSON on the topic `tof/matrice/post`.

### 5. Install the server dependencies (PC)

```bash
pip install fastapi uvicorn paho-mqtt
```

### 6. Run the MQTT broker (Mosquitto)

Install Mosquitto (https://mosquitto.org/download), then run it with the project config:

```bash
& "C:\Program Files\mosquitto\mosquitto.exe" -c "path\to\mosquitto.conf" -v
```

`mosquitto.conf`:
```
listener 1883 0.0.0.0
allow_anonymous true
```

> **Windows gotcha:** Mosquitto installs a service that auto-starts with the default (localhost-only) config and occupies port 1883, which conflicts with our own instance and silently splits clients across two brokers. Set the service to manual (`Set-Service -Name mosquitto -StartupType Manual`, admin), or kill the stray process (`netstat -ano | findstr :1883` then `taskkill /PID <pid> /F`).

### 7. Run the web server

From the folder containing `app.py`, `index.html`, `history.html`:

```bash
python app.py
```

- Live view: http://localhost:8000
- History: http://localhost:8000/history

The SQLite database (`passages.db`) is created automatically on first run.

## Network requirement

The ESP32 and the machine running Mosquitto **must be on the same local network** (same subnet), and the network must not isolate clients from each other. University/enterprise networks usually block this. The simplest reliable setup for development is a **phone hotspot**: connect both the PC and the ESP to it.

> The PC's IP on the hotspot may change between sessions. If it stops working, run `ipconfig`, update `MQTT_BROKER` in `secrets.py`, and redeploy `secrets.py` to the board.

> The ESP32 only supports **2.4 GHz** WiFi, not 5 GHz.

## Useful commands

```bash
mpremote connect list                       # find the board's COM port (VID 303a:)
mpremote connect COM6 repl                  # open the REPL (Ctrl+C to interrupt, Ctrl+X to exit)
mpremote connect COM6 run script.py         # run a PC script on the board without installing it
mpremote connect COM6 cp file.py :file.py   # copy a file to the board
mpremote connect COM6 fs ls                 # list files on the board
```

## Configuration (server-side)

In `app.py`:
- `SEUIL_RATIO` — counting sensitivity (lower = less sensitive).
- `CALIB_FRAMES` — number of frames averaged for the resting-distance calibration.
- `TIMEOUT_PASSAGE_S` — max delay between the two zones being triggered for a valid passage.

Recalibration can also be triggered live from the web UI ("Recalibrer" button).

## Known limitations

- The counting algorithm is a simple two-zone state machine (left/right halves of the matrix). It does not yet handle two people crossing simultaneously, or someone turning back mid-passage.
- Multi-sensor / multi-room support: the data schema already includes `sensor` and `room` fields, but the server currently processes a single sensor. Routing per sensor/room is future work.
- No automatic MQTT/WiFi reconnection on the ESP or the server (fine for a prototype).
- Timestamps in the database are stored in UTC.