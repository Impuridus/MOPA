// Preferences are persisted by Python; JavaScript updates the interface.
let preferences = { language: "en", temperature: "fahrenheit", theme: "dark" };
let statusKey = "loading";
let initialized = false;
let loading = false;
const fields = ["language", "temperature", "theme"];
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
    // These remain sample readings until the weather feature is connected.
    document.getElementById("temperature").textContent = formatTemperature(72);
    document.getElementById("feels-temperature").textContent = formatTemperature(74);
    document.getElementById("high-low").textContent = `${text("high")}: ${formatTemperature(76)} · ${text("low")}: ${formatTemperature(63)}`;
    document.getElementById("wind-value").textContent = `8 ${text("mph")}`;
    document.getElementById("settings-status").textContent = text(statusKey);
    updateClock();
}

function showPanel(name) {
    ["welcome", "weather", "settings"].forEach(panel => {
        document.getElementById(`${panel}-panel`).hidden = panel !== name;
    });
    ["weather", "settings"].forEach(panel => {
        const button = document.getElementById(`${panel}-button`);
        button.classList.toggle("active", panel === name);
        if (panel === name) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });
    document.querySelector(`#${name}-panel h1`).focus();
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

["weather", "settings"].forEach(name => {
    document.getElementById(`${name}-button`).addEventListener("click", () => showPanel(name));
});
fields.forEach(key => controls[key].addEventListener("change", () => changePreference(key)));
document.getElementById("retry-button").addEventListener("click", loadSettings);
window.addEventListener("pywebviewready", loadSettings);
render();
loadSettings();
setInterval(updateClock, 1000);
