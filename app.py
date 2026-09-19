"""
DHT11 Sensor Dashboard
======================
Flask web app that reads temperature & humidity readings from Firebase
Realtime Database and serves a live-updating dashboard (AJAX polling every
5 seconds, Chart.js graph, buzzer status icon).

This app does NOT talk to any sensor or GPIO pin directly. The actual
Raspberry Pi with the DHT11 sensor and buzzer runs `pi_sensor.py` on its
own, and pushes readings to Firebase. This app (which can run anywhere --
a laptop, a cloud server, Render, etc.) only reads what's already in
Firebase and displays it.

    [ Raspberry Pi ]                [ Firebase RTDB ]              [ This app ]
    pi_sensor.py  -- writes -->  "live" / "history"  -- reads -->   app.py

Design note: earlier versions of this file used a background thread to
poll Firebase every few seconds. That was removed -- on hosts like Render
(gunicorn), background threads can behave unpredictably depending on
worker/fork timing, which made this hard to debug. Now each API request
just reads directly from Firebase. Simpler and more reliable, at the cost
of a small amount of extra latency per request (fine for a 5s-poll
dashboard).

SOFTWARE SETUP
--------------
1. pip install -r requirements.txt
2. Set up Firebase read access:
     - Project Settings -> Service Accounts -> Generate new private key
       (must be from the SAME Firebase project pi_sensor.py is using)
     - Save the JSON as `serviceAccountKey.json` in this folder, OR
       set the FIREBASE_KEY_JSON env var to the full JSON contents
       (this is what you do on Render -- see Environment tab)
     - Set FIREBASE_DB_URL below (or as an env var) to your database URL
3. python app.py
4. Open http://<host>:5000 in a browser
"""

import os
import json as _json
from datetime import datetime

from flask import Flask, jsonify, render_template

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 5          # how often the frontend polls this app
BUZZER_TEMP_THRESHOLD_C = 38.0     # only used to label the dashboard; the
                                    # actual buzzer decision happens on the Pi

FIREBASE_DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://dht11-dashboard-2acac-default-rtdb.asia-southeast1.firebasedatabase.app/",
)
FIREBASE_KEY_PATH = os.environ.get(
    "FIREBASE_KEY_PATH",
    os.path.join(os.path.dirname(__file__), "serviceAccountKey.json"),
)
FIREBASE_KEY_JSON = os.environ.get("FIREBASE_KEY_JSON")

# --------------------------------------------------------------------------
# Firebase setup (read-only usage from this app's side)
# --------------------------------------------------------------------------
FIREBASE_READY = False
live_ref = None
history_ref = None
try:
    import firebase_admin
    from firebase_admin import credentials, db as firebase_db

    if FIREBASE_KEY_JSON:
        cred = credentials.Certificate(_json.loads(FIREBASE_KEY_JSON))
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        live_ref = firebase_db.reference("live")
        history_ref = firebase_db.reference("history")
        FIREBASE_READY = True
        print("[firebase] initialized using FIREBASE_KEY_JSON env var", flush=True)
    elif os.path.exists(FIREBASE_KEY_PATH):
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        live_ref = firebase_db.reference("live")
        history_ref = firebase_db.reference("history")
        FIREBASE_READY = True
        print(f"[firebase] initialized using key file at {FIREBASE_KEY_PATH}", flush=True)
    else:
        print(f"[firebase] NOT initialized: no FIREBASE_KEY_JSON env var set, "
              f"and no key file found at {FIREBASE_KEY_PATH}.", flush=True)
except Exception as exc:
    print(f"[firebase] init failed: {exc}", flush=True)

# --------------------------------------------------------------------------
# Flask app
# --------------------------------------------------------------------------
app = Flask(__name__)


def _to_display_reading(fb_reading):
    """Translate pi_sensor.py's field names into the names the dashboard
    template/frontend expects."""
    if not fb_reading:
        return None
    ts = fb_reading.get("timestamp")
    return {
        "temperature": fb_reading.get("temperature_c"),
        "humidity": fb_reading.get("humidity_pct"),
        "buzzer_on": fb_reading.get("buzzer_active", False),
        "timestamp": datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else None,
        "hardware_ok": fb_reading.get("hardware_ok", False),
    }


EMPTY_READING = {
    "temperature": None,
    "humidity": None,
    "buzzer_on": False,
    "timestamp": None,
    "hardware_ok": False,
}


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        threshold=BUZZER_TEMP_THRESHOLD_C,
        interval=POLL_INTERVAL_SECONDS,
        simulate=not FIREBASE_READY,
    )


@app.route("/api/current")
def api_current():
    if not FIREBASE_READY:
        return jsonify(EMPTY_READING)
    try:
        live_data = live_ref.get()
        reading = _to_display_reading(live_data)
        return jsonify(reading or EMPTY_READING)
    except Exception as exc:
        print(f"[firebase] /api/current read failed: {exc}", flush=True)
        return jsonify(EMPTY_READING)


@app.route("/api/history")
def api_history():
    if not FIREBASE_READY:
        return jsonify([])
    try:
        history_data = history_ref.get() or []
        display_history = [
            r for r in (_to_display_reading(h) for h in history_data) if r
        ]
        return jsonify(display_history)
    except Exception as exc:
        print(f"[firebase] /api/history read failed: {exc}", flush=True)
        return jsonify([])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)