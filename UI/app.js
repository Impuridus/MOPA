// Preferences are persisted by Python; JavaScript updates the interface.
let preferences = { language: "en", temperature: "fahrenheit", theme: "dark", calendar: "gregorian" };
let statusKey = "loading";
let initialized = false;
let loading = false;
const fields = ["language", "temperature", "theme", "calendar"];
const controls = Object.fromEntries(fields.map(key => [key, document.getElementById(`${key}-select`)]));
const text = key => translations[preferences.language][key];

function updateClock() {
    const now = new Date();
    document.getElementById("current-time").textContent = now.toLocaleTimeString(preferences.language, {
        hour: "numeric", minute: "2-digit",
    });
    document.getElementById("current-date").textContent = now.toLocaleDateString(preferences.language, {
        weekday: "long", month: "short", day: "numeric", year: "numeric",
    });
}

function formatTemperature(fahrenheit) {
    if (fahrenheit == null || !Number.isFinite(fahrenheit)) return "—";
    const value = preferences.temperature === "celsius" ? (fahrenheit - 32) * 5 / 9 : fahrenheit;
    const unit = preferences.temperature === "celsius" ? "C" : "F";
    return `${new Intl.NumberFormat(preferences.language, { maximumFractionDigits: 0 }).format(value)}°${unit}`;
}

function render() {
    document.documentElement.lang = preferences.language;
    document.documentElement.dataset.theme = preferences.theme;
    document.querySelectorAll("[data-i18n]").forEach(element => {
        element.textContent = text(element.dataset.i18n);
    });
    document.getElementById("feature-nav").setAttribute("aria-label", text("features"));
    fields.forEach(key => { controls[key].value = preferences[key]; });
    renderWeather();
    document.getElementById("settings-status").textContent = text(statusKey);
    updateClock();
    calendarUI.settingsChanged();
}

function showPanel(name) {
    if (name !== "calendar" && !document.getElementById("calendar-panel").hidden && !calendarUI.allowLeave()) return;
    ["welcome", "workout", "diet", "weather", "music", "calendar", "settings"].forEach(panel => {
        document.getElementById(`${panel}-panel`).hidden = panel !== name;
    });
    ["workout", "diet", "weather", "music", "calendar", "settings"].forEach(panel => {
        const button = document.getElementById(`${panel}-button`);
        button.classList.toggle("active", panel === name);
        if (panel === name) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });
    const panelHeading = document.querySelector(`#${name}-panel h1`);
    (panelHeading || document.getElementById(`${name}-panel`)).focus();
    if (name === "weather") loadWeather();
    if (name === "calendar") calendarUI.open();
}

function disableControls(disabled) {
    Object.values(controls).forEach(control => { control.disabled = disabled; });
}

async function loadSettings() {
    if (loading || initialized || !window.pywebview?.api) return;
    loading = true;
    document.getElementById("retry-button").hidden = true;
    statusKey = "loading";
    render();
    try {
        preferences = await window.pywebview.api.get_settings();
        initialized = true;
        statusKey = "saved";
        disableControls(false);
    } catch (error) {
        console.error(error);
        statusKey = "loadError";
        document.getElementById("retry-button").hidden = false;
    } finally {
        loading = false;
        render();
    }
}

async function changePreference(key) {
    const previous = { ...preferences };
    preferences = { ...preferences, [key]: controls[key].value };
    statusKey = "saving";
    disableControls(true); // Serialize saves so rapid changes cannot overwrite each other.
    render();
    try {
        preferences = await window.pywebview.api.save_settings({ ...preferences });
        statusKey = "saved";
    } catch (error) {
        console.error(error);
        preferences = previous;
        statusKey = "saveError";
    } finally {
        render();
        disableControls(false);
        controls[key].focus();
    }
}

let weatherReport = null;
let weatherBusy = false;
let weatherError = false;

function conditionName(code, isDay) {
    const codes = {
        0: isDay === 0 ? "Clear night" : "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        56: "Light freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
        77: "Snow grains", 80: "Light rain showers", 81: "Rain showers", 82: "Heavy rain showers",
        85: "Light snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
        96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    };
    return codes[code] ?? "Conditions unavailable";
}

function renderWeather() {
    const set = (id, value) => { document.getElementById(id).textContent = value; };
    const button = document.getElementById("refresh-weather");
    button.disabled = weatherBusy;
    button.textContent = weatherBusy ? "Refreshing…" : "Refresh";
    if (!weatherReport) {
        ["temperature", "feels-temperature", "humidity-value", "wind-value", "weather-condition", "high-low"].forEach(id => set(id, "—"));
        set("weather-status", weatherBusy ? "Loading weather…" : weatherError ? "Weather unavailable. Check your connection and select Refresh to retry." : "Open Weather to load current conditions.");
        return;
    }
    const { current, daily } = weatherReport.data;
    set("temperature", formatTemperature(current.temperature_2m));
    set("feels-temperature", formatTemperature(current.apparent_temperature));
    set("weather-condition", conditionName(current.weather_code, current.is_day));
    set("humidity-value", current.relative_humidity_2m == null ? "—" : `${current.relative_humidity_2m}%`);
    set("wind-value", current.wind_speed_10m == null ? "—" : `${current.wind_speed_10m} ${text("mph")}`);
    const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    set("wind-direction", current.wind_direction_10m == null ? "" : `From ${directions[Math.round(current.wind_direction_10m / 45) % 8]}`);
    set("high-low", `${daily.time[0]} · ${text("high")}: ${formatTemperature(daily.temperature_2m_max[0])} · ${text("low")}: ${formatTemperature(daily.temperature_2m_min[0])}`);
    const fetched = new Date(weatherReport.fetched * 1000).toLocaleString(preferences.language, { timeZone: "America/New_York" });
    const stale = weatherReport.stale || weatherError || Date.now() / 1000 - weatherReport.fetched > 1200;
    const state = weatherBusy ? "Refreshing — showing saved report." : stale ? "Could not get a fresh report — showing saved weather." : "Latest available report.";
    set("weather-status", `${state} Conditions: ${current.time.replace("T", " ")}. Retrieved: ${fetched}.${weatherReport.cache_saved === false ? " Could not save for offline use." : ""}`);
}

async function loadWeather() {
    if (weatherBusy || !window.pywebview?.api) return;
    weatherBusy = true;
    weatherError = false;
    renderWeather();
    try {
        weatherReport = await window.pywebview.api.get_weather();
    } catch (error) {
        console.error(error);
        weatherError = true;
    } finally {
        weatherBusy = false;
        renderWeather();
    }
}

document.getElementById("refresh-weather").addEventListener("click", loadWeather);
window.addEventListener("pywebviewready", () => {
    if (!document.getElementById("weather-panel").hidden) loadWeather();
});
setInterval(() => {
    if (!document.getElementById("weather-panel").hidden) loadWeather();
}, 10 * 60 * 1000);


["workout", "diet", "weather", "music", "calendar", "settings"].forEach(name => {
    document.getElementById(`${name}-button`).addEventListener("click", () => showPanel(name));
});
fields.forEach(key => controls[key].addEventListener("change", () => changePreference(key)));
document.getElementById("retry-button").addEventListener("click", loadSettings);
window.addEventListener("pywebviewready", loadSettings);
render();
loadSettings();
setInterval(updateClock, 1000);
