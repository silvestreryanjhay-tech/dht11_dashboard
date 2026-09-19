"""
Sensor Publisher - RUN THIS ONE IN THONNY, on the Raspberry Pi that has the
DHT11 sensor and buzzer wired up.
 
What it does:
  1. Reads the DHT11 temperature/humidity sensor.
  2. Turns the buzzer on/off locally (no internet needed for this part - it
     works even if Wi-Fi drops).
  3. Pushes every reading straight to Firebase Realtime Database, so the
     website (app.py, running anywhere) can display it live.
 
The website never talks to the GPIO pins directly - this script is the only
thing that does, and Firebase is the "middleman" between this script and the
browser.
 
If Firebase ever fails (bad credentials, no internet, wrong project) this
script keeps running and keeps controlling the buzzer locally - it just
skips the upload for that cycle and prints a warning, instead of crashing.
 
----------------------------------------------------------------------------
ONE-TIME SETUP
----------------------------------------------------------------------------
1. In the Firebase console: Project settings (gear icon) -> Service accounts
   -> Generate new private key. This downloads a .json file.
   Rename it to `serviceAccountKey.json` and put it in this SAME folder as
   this script. Keep this file private - never upload it to GitHub or share
   it publicly; it can write to your whole database.
 
   IMPORTANT: the key must come from the SAME Firebase project as
   DATABASE_URL below. If they don't match, every write will fail with a
   401 Unauthorized error (this script will now check that automatically
   at startup and print a clear warning if they don't match).
 
2. DATABASE_URL below is already filled in for this project. If you ever
   move to a different Firebase project, copy the new URL from
   Build -> Realtime Database in the Firebase console.
 
3. Install dependencies on the Pi (in a terminal, not Thonny):
       pip install firebase-admin gpiozero adafruit-circuitpython-dht adafruit-blinka --break-system-packages
 
4. Check/adjust the wiring pin in the CONFIG block below if yours differs
   from the README's wiring table.
 
5. Open this file in Thonny and press Run (F5, green play button).
   Press Stop to end it cleanly (turns the buzzer off and releases GPIO).
----------------------------------------------------------------------------
"""
import json
import time
from collections import deque
 
import firebase_admin
from firebase_admin import credentials, db
 
# ----------------------------------------------------------------------------
# CONFIG - fill these in before running
# ----------------------------------------------------------------------------
SERVICE_ACCOUNT_KEY_PATH = "serviceAccountKey.json"
DATABASE_URL = "https://dht11-dashboard-2acac-default-rtdb.asia-southeast1.firebasedatabase.app/"
 
DHT_PIN_BOARD_ATTR = "D4"   # board.D4 -> GPIO4 (BCM)
BUZZER_PIN = 18             # BCM numbering
 
BUZZER_TEMP_THRESHOLD_C = 38.0   # must match BUZZER_TEMP_THRESHOLD_C in app.py
SAMPLE_INTERVAL_SEC = 5.0        # how often to read + publish
HISTORY_LENGTH = 30              # samples kept for the website's graph
 
# ----------------------------------------------------------------------------
# FIREBASE INIT
# ----------------------------------------------------------------------------
FIREBASE_READY = False
try:
    # Sanity check: does the key's project match the DATABASE_URL?
    with open(SERVICE_ACCOUNT_KEY_PATH) as key_file:
        key_project_id = json.load(key_file).get("project_id", "")
    if key_project_id and key_project_id not in DATABASE_URL:
        print(
            f"[firebase] WARNING: serviceAccountKey.json is for project "
            f"'{key_project_id}', but DATABASE_URL points somewhere else. "
            f"This WILL cause 401 Unauthorized errors. Re-download the key "
            f"from the correct Firebase project (Project settings -> "
            f"Service accounts -> Generate new private key)."
        )
 
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
    live_ref = db.reference("live")
    history_ref = db.reference("history")
    FIREBASE_READY = True
except Exception as exc:
    print(f"[firebase] init failed, will run in local-only mode: {exc}")
    live_ref = None
    history_ref = None
 
 
def push_live(payload):
    if not FIREBASE_READY:
        return
    try:
        live_ref.set(payload)
    except Exception as exc:
        print(f"[firebase] live push failed (check credentials/rules): {exc}")
 
 
def push_history(payload_list):
    if not FIREBASE_READY:
        return
    try:
        history_ref.set(payload_list)
    except Exception as exc:
        print(f"[firebase] history push failed (check credentials/rules): {exc}")
 
 
# ----------------------------------------------------------------------------
# HARDWARE SETUP
# ----------------------------------------------------------------------------
import board  # noqa: E402
import adafruit_dht  # noqa: E402
from gpiozero import Buzzer  # noqa: E402
 
dht_device = adafruit_dht.DHT11(getattr(board, DHT_PIN_BOARD_ATTR), use_pulseio=False)
buzzer = Buzzer(BUZZER_PIN)
 
# ----------------------------------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------------------------------
history_buffer = deque(maxlen=HISTORY_LENGTH)
 
print("Sensor publisher running. Press Stop in Thonny to end.")
time.sleep(2)  # let the DHT11 settle before the first read
try:
    while True:
        try:
            temperature_c = dht_device.temperature
            humidity_pct = dht_device.humidity
        except RuntimeError as exc:
            # DHT11 misfires happen often - just skip this cycle and retry.
            print(f"[sensor] read failed, retrying next cycle: {exc}")
            time.sleep(SAMPLE_INTERVAL_SEC)
            continue
 
        if temperature_c is None or humidity_pct is None:
            time.sleep(SAMPLE_INTERVAL_SEC)
            continue
 
        buzzer_active = temperature_c >= BUZZER_TEMP_THRESHOLD_C
        buzzer.on() if buzzer_active else buzzer.off()
 
        now = time.time()
        history_buffer.append({"temperature_c": temperature_c, "humidity_pct": humidity_pct, "t": now})
 
        push_live(
            {
                "temperature_c": temperature_c,
                "humidity_pct": humidity_pct,
                "buzzer_active": buzzer_active,
                "timestamp": now,
                "hardware_ok": True,
            }
        )
        push_history(list(history_buffer))
 
        status = "ONLINE" if FIREBASE_READY else "LOCAL-ONLY (firebase not connected)"
        print(f"T={temperature_c:>5.1f} C   H={humidity_pct:>5.1f} %   buzzer={'ON' if buzzer_active else 'off'}   [{status}]")
        time.sleep(SAMPLE_INTERVAL_SEC)
 
except KeyboardInterrupt:
    pass
finally:
    print("Stopping - turning off buzzer and releasing GPIO.")
    buzzer.off()
    buzzer.close()
    dht_device.exit()

