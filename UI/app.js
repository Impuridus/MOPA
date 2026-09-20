const timeElement = document.getElementById("current-time");
const dateElement = document.getElementById("current-date");

const weatherButton = document.getElementById("weather-button");
const welcomePanel = document.getElementById("welcome-panel");
const weatherPanel = document.getElementById("weather-panel");

function updateClock() {
    const now = new Date();

    timeElement.textContent = now.toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });

    dateElement.textContent = now.toLocaleDateString([], {
        weekday: "long",
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function showWeather() {
    welcomePanel.hidden = true;
    weatherPanel.hidden = false;

    weatherButton.classList.add("active");
    weatherButton.setAttribute("aria-current", "page");
}

weatherButton.addEventListener("click", showWeather);

updateClock();
setInterval(updateClock, 1000);