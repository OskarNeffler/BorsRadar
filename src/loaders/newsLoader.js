// src/loaders/newsLoader.js
import { waait, cacheNewsData, getCachedNews } from "../helpers";
import { toast } from "react-toastify";

export async function newsLoader() {
  console.log("NewsLoader: Starting loader function");

  // Kolla om vi har cachade nyheter först
  const cachedNews = getCachedNews();
  if (cachedNews) {
    console.log("NewsLoader: Using cached news", cachedNews);
    return { newsData: cachedNews };
  }

  try {
    console.log("NewsLoader: Attempting to fetch news from API");

    // Använd direkt URL till ditt news_articles API
    const apiUrl = "http://13.61.135.153:8000/news-articles";

    // Öka timeout och lägg till mer detaljerad felhantering
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 sekunders timeout

    const response = await fetch(apiUrl, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    console.log("NewsLoader: Response status", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("NewsLoader: Error response text", errorText);
      throw new Error(`Could not fetch news: ${response.status} ${errorText}`);
    }

    // API förväntas returnera ett objekt med news_articles
    const data = await response.json();

    // Mappa om artiklarna till det format som din frontend förväntar sig
    const newsData = (data.news_articles || []).map((article) => ({
      id: article.id,
      title: article.title,
      summary: article.summary || "",
      url: article.url || "#",
      imageUrl: article.image_url || null,
      publishedAt: article.published_at,
      source: article.source || "Börsnyheter",
      content: article.content || "",
    }));

    console.log("NewsLoader: Fetched news data", newsData);

    if (newsData.length === 0) {
      console.warn("NewsLoader: Received empty news data");
      toast.warn("Inga nyheter hittades");
    } else {
      // Cacha endast om vi har faktiska data
      cacheNewsData(newsData);
    }

    return { newsData };
  } catch (error) {
    console.error("NewsLoader: Detailed error", {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });

    // Mer specifik felhantering
    if (error.name === "AbortError") {
      toast.error("Nyhetshämtning timeout");
    } else if (error.name === "TypeError") {
      toast.error("Nätverksfel. Kontrollera din anslutning.");
    } else {
      toast.error(`Kunde inte hämta nyheter: ${error.message}`);
    }

    return { newsData: [] };
  }
}
