const POLL_INTERVAL_MS = 5000;

const tempValueEl = document.getElementById("temp-value");
const humidityValueEl = document.getElementById("humidity-value");
const buzzerCardEl = document.getElementById("buzzer-card");
const buzzerStatusEl = document.getElementById("buzzer-status");
const lastUpdatedEl = document.getElementById("last-updated");

const ctx = document.getElementById("historyChart").getContext("2d");
const chart = new Chart(ctx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "Temperature (°C)",
        data: [],
        borderColor: "#38bdf8",
        backgroundColor: "rgba(56,189,248,0.15)",
        tension: 0.3,
        yAxisID: "y",
      },
      {
        label: "Humidity (%)",
        data: [],
        borderColor: "#34d399",
        backgroundColor: "rgba(52,211,153,0.15)",
        tension: 0.3,
        yAxisID: "y1",
      },
    ],
  },
  options: {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    scales: {
      y: {
        type: "linear",
        position: "left",
        title: { display: true, text: "°C" },
        grid: { color: "#334155" },
        ticks: { color: "#94a3b8" },
      },
      y1: {
        type: "linear",
        position: "right",
        title: { display: true, text: "%" },
        grid: { drawOnChartArea: false },
        ticks: { color: "#94a3b8" },
      },
      x: {
        ticks: { color: "#94a3b8", maxRotation: 0 },
        grid: { color: "#1e293b" },
      },
    },
    plugins: {
      legend: { labels: { color: "#e2e8f0" } },
    },
  },
});

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function updateCards(reading) {
  if (reading.temperature === null || reading.temperature === undefined) return;

  tempValueEl.textContent = reading.temperature.toFixed(1);
  humidityValueEl.textContent = reading.humidity.toFixed(1);

  if (reading.buzzer_on) {
    buzzerCardEl.classList.add("active");
    buzzerStatusEl.textContent = "SOUNDING";
  } else {
    buzzerCardEl.classList.remove("active");
    buzzerStatusEl.textContent = "OFF";
  }

  lastUpdatedEl.textContent = "Last updated: " + formatTime(reading.timestamp);
}

function updateChartFromHistory(readings) {
  chart.data.labels = readings.map((r) => formatTime(r.timestamp));
  chart.data.datasets[0].data = readings.map((r) => r.temperature);
  chart.data.datasets[1].data = readings.map((r) => r.humidity);
  chart.update("none");
}

async function pollCurrent() {
  try {
    const res = await fetch("/api/current");
    const data = await res.json();
    updateCards(data);
  } catch (err) {
    console.error("Failed to fetch current reading:", err);
  }
}

async function pollHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    updateChartFromHistory(data);
  } catch (err) {
    console.error("Failed to fetch history:", err);
  }
}

function poll() {
  pollCurrent();
  pollHistory();
}

poll();
setInterval(poll, POLL_INTERVAL_MS);
