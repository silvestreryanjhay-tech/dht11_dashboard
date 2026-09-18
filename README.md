# DHT11 Sensor Dashboard

A Python (Flask) web app that monitors a DHT11 temperature/humidity sensor,
sounds a buzzer past 38°C, and shows live readings + a history graph in the
browser — auto-refreshing every 5 seconds via AJAX, no page reload.

## Features
- ✅ Live temperature & humidity readings, updated every 5s (fetch/AJAX)
- ✅ Chart.js line graph plotting temperature + humidity history
- ✅ Buzzer auto-activates at 38°C (GPIO), with an animated on-screen icon
- ✅ Optional Firebase Realtime Database logging of every reading
- ✅ Runs in "simulated data" mode automatically if no sensor/board is
  detected, so you can test the site on a laptop before wiring the Pi

## 1. Hardware wiring (Raspberry Pi)

| Component      | Pi Pin (BCM) |
|-----------------|--------------|
| DHT11 DATA      | GPIO4        |
| DHT11 VCC       | 3.3V or 5V (check your module) |
| DHT11 GND       | GND          |
| Buzzer +        | GPIO18       |
| Buzzer -        | GND          |

If your DHT11 module doesn't already have a pull-up resistor built in,
add a 10kΩ resistor between DATA and VCC.

If you're using a passive/high-current buzzer, drive it through a small
NPN transistor (e.g. 2N2222) or a relay instead of straight off the GPIO pin.

## 2. Install

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

On the Raspberry Pi you'll also need:
```bash
sudo apt-get update
sudo apt-get install libgpiod2
```

## 3. (Optional) Firebase setup

1. Go to the [Firebase console](https://console.firebase.google.com), create
   a project, then enable **Realtime Database**.
2. Project settings → **Service accounts** → **Generate new private key**.
   This downloads a JSON file.
3. Rename it `firebase_key.json` and place it in this folder.
4. Set your database URL as an environment variable (or edit
   `FIREBASE_DB_URL` directly in `app.py`):
   ```bash
   export FIREBASE_DB_URL="https://YOUR-PROJECT-default-rtdb.firebaseio.com"
   ```

If you skip this step entirely, the app still works — it just won't
log readings to the cloud, and `FIREBASE_READY` stays `False`.

## 4. Run

```bash
python app.py
```

Then open `http://<raspberry-pi-ip>:5000` (or `http://localhost:5000` if
running on the same machine) in a browser.

## How the pieces fit together

- `app.py` — Flask server. A background thread reads the sensor every
  5 seconds, updates the buzzer via GPIO, stores the last 100 readings in
  memory, and (optionally) pushes each reading to Firebase.
- `/api/current` — JSON endpoint returning the latest reading + buzzer state.
- `/api/history` — JSON endpoint returning the recent reading history for
  the graph.
- `static/js/dashboard.js` — polls both endpoints every 5 seconds with
  `fetch()` and updates the DOM + Chart.js graph without reloading the page.
- `templates/index.html` / `static/css/style.css` — the dashboard UI,
  including the SVG buzzer icon that turns red and shakes when active.

## Customizing

- Change the trip point: edit `BUZZER_TEMP_THRESHOLD_C` in `app.py`.
- Change the polling/sampling rate: edit `READ_INTERVAL_SECONDS` in
  `app.py` **and** `POLL_INTERVAL_MS` in `dashboard.js` (keep them equal).
- Change how many points the graph keeps: `HISTORY_MAX_POINTS` in `app.py`.

## Notes for your report/documentation

This satisfies the four requirements commonly asked for in DHT11 web
dashboard projects:
1. **Auto-update every 5s without refresh** — done via `fetch()` polling in
   `dashboard.js` (AJAX), not a full page reload.
2. **Python website to control/monitor the sensor** — Flask app (`app.py`)
   serves the site and directly reads the GPIO-connected DHT11.
3. **Graph of sensor readings** — Chart.js line chart in `index.html` /
   `dashboard.js`, fed by `/api/history`.
4. **Buzzer at 38°C + on-screen icon** — GPIO buzzer control in `app.py`'s
   `sensor_loop()`, with the SVG icon in `index.html` turning red/shaking
   via the `.active` class in `style.css` whenever `buzzer_on` is true.
