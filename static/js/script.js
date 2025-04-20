/** @format */

// Reemplaza esto con tu clave de API de YouTube
const API_KEY = "AIzaSyAF0pP0QpfosKStRk_lQX3zoTNHHbmqF2A";

async function searchVideos() {
  const searchInput = document.getElementById("searchInput").value;
  const resultsContainer = document.getElementById("searchResults");

  // Add this line to ensure grid layout is visible
  resultsContainer.className = "debug-grid";

  try {
    const response = await fetch(
      `https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=12&q=${encodeURIComponent(
        searchInput
      )}&type=video&key=${API_KEY}`
    );
    const data = await response.json();

    resultsContainer.innerHTML = data.items
      .map(
        (item) => `
          <div class="video-card">
            <img 
              src="${item.snippet.thumbnails.high.url}"
              alt="${item.snippet.title}"
              class="thumbnail"
            />
            <div class="video-info">
              <div class="video-title">${item.snippet.title}</div>
              <button 
                onclick="copyVideoUrl('https://www.youtube.com/watch?v=${item.id.videoId}')"
                class="copy-link"
              >
                Copiar enlace
              </button>
            </div>
          </div>
        `
      )
      .join("");
  } catch (error) {
    console.error("Error al buscar videos:", error);
    resultsContainer.innerHTML =
      "<p>Error al buscar videos. Por favor, intenta de nuevo.</p>";
  }
  document.getElementById("searchResults").style.margin = "2rem 0";
}

function copyVideoUrl(url) {
  const urlInput = document.getElementById("video_url");
  urlInput.value = url;
  urlInput.scrollIntoView({ behavior: "smooth" });
  urlInput.focus();
}

// Evento para buscar al presionar Enter
document
  .getElementById("searchInput")
  .addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      searchVideos();
    }
  });
