"""
DHT11 Sensor Dashboard
======================
Flask web app that reads temperature & humidity from a DHT11 sensor,
drives a buzzer when temperature hits a threshold, logs readings to
Firebase Realtime Database, and serves a live-updating dashboard
(AJAX polling every 5 seconds, Chart.js graph, buzzer status icon).

HARDWARE WIRING (Raspberry Pi)
-------------------------------
DHT11 data pin  -> GPIO4   (BCM numbering, with a 10k pull-up resistor
                             between DATA and VCC if your module has no
                             built-in pull-up)
Buzzer (+)      -> GPIO18  (through a transistor/relay if it's a
                             passive/high-current buzzer; a small active
                             buzzer can be driven directly)
Buzzer (-)      -> GND

SOFTWARE SETUP
--------------
1. pip install -r requirements.txt
2. (Optional but recommended) Set up Firebase:
     - Create a Firebase project -> Realtime Database
     - Project Settings -> Service Accounts -> Generate new private key
     - Save the JSON as `firebase_key.json` in this folder
     - Set FIREBASE_DB_URL below (or as an env var) to your database URL,
       e.g. https://your-project-id-default-rtdb.asia-southeast1.firebasedatabase.app
   If you skip this, the app still runs fine and just keeps history in memory.
3. python app.py
4. Open http://<raspberry-pi-ip>:5000 in a browser
"""

import os
import time
import threading
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
READ_INTERVAL_SECONDS = 5          # how often we sample the sensor
BUZZER_TEMP_THRESHOLD_C = 38.0     # buzzer turns on at/above this temp
HISTORY_MAX_POINTS = 100           # how many points the graph keeps
DHT_PIN = 4                        # BCM GPIO pin for the DHT11 data line
BUZZER_PIN = 18                    # BCM GPIO pin for the buzzer

FIREBASE_DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://YOUR-PROJECT-ID-default-rtdb.firebaseio.com",
)
FIREBASE_KEY_PATH = os.environ.get(
    "FIREBASE_KEY_PATH",
    os.path.join(os.path.dirname(__file__), "firebase_key.json"),
)

# --------------------------------------------------------------------------
# Optional hardware / Firebase imports.
# The app degrades gracefully (simulated data, no cloud logging) if these
# libraries or the actual hardware aren't present -- handy for developing
# on a laptop before deploying to the Raspberry Pi.
# --------------------------------------------------------------------------
SIMULATE = False

try:
    import board
    import adafruit_dht
    dht_device = adafruit_dht.DHT11(board.D4)
    HAS_SENSOR = True
except Exception:
    HAS_SENSOR = False
    SIMULATE = True

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    HAS_GPIO = True
except Exception:
    HAS_GPIO = False

try:
    import firebase_admin
    from firebase_admin import credentials, db as firebase_db
    if os.path.exists(FIREBASE_KEY_PATH):
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        FIREBASE_READY = True
    else:
        FIREBASE_READY = False
except Exception:
    FIREBASE_READY = False

# --------------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------------
app = Flask(__name__)
lock = threading.Lock()

latest_reading = {
    "temperature": None,
    "humidity": None,
    "buzzer_on": False,
    "timestamp": None,
}

history = deque(maxlen=HISTORY_MAX_POINTS)


def set_buzzer(is_on: bool):
    if HAS_GPIO:
        GPIO.output(BUZZER_PIN, GPIO.HIGH if is_on else GPIO.LOW)


def read_sensor():
    """Return (temperature_c, humidity_pct) or (None, None) on failure."""
    if HAS_SENSOR:
        try:
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            if temperature is not None and humidity is not None:
                return round(temperature, 1), round(humidity, 1)
        except RuntimeError:
            # DHT sensors misfire fairly often -- just skip this cycle
            return None, None
    if SIMULATE:
        import random
        temperature = round(random.uniform(24, 40), 1)
        humidity = round(random.uniform(40, 70), 1)
        return temperature, humidity
    return None, None


def push_to_firebase(reading):
    if not FIREBASE_READY:
        return
    try:
        ref = firebase_db.reference("dht11_readings")
        ref.push(reading)
    except Exception as exc:
        print(f"[firebase] failed to push reading: {exc}")


def sensor_loop():
    while True:
        temperature, humidity = read_sensor()
        if temperature is not None:
            buzzer_on = temperature >= BUZZER_TEMP_THRESHOLD_C
            set_buzzer(buzzer_on)

            reading = {
                "temperature": temperature,
                "humidity": humidity,
                "buzzer_on": buzzer_on,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }

            with lock:
                latest_reading.update(reading)
                history.append(reading)

            push_to_firebase(reading)

        time.sleep(READ_INTERVAL_SECONDS)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        threshold=BUZZER_TEMP_THRESHOLD_C,
        interval=READ_INTERVAL_SECONDS,
        simulate=SIMULATE,
    )


@app.route("/api/current")
def api_current():
    with lock:
        return jsonify(latest_reading)


@app.route("/api/history")
def api_history():
    with lock:
        return jsonify(list(history))


if __name__ == "__main__":
    threading.Thread(target=sensor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
