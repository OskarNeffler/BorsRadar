// src/loaders/newsLoader.js
import { waait, cacheNewsData, getCachedNews } from "../helpers";
import { toast } from "react-toastify";

export async function newsLoader() {
  console.log("NewsLoader: Starting loader function");

  // Always log to help with debugging
  await waait(500);

  // Check for cached news first
  const cachedNews = getCachedNews();
  if (cachedNews) {
    console.log("NewsLoader: Using cached news", cachedNews);
    return { newsData: cachedNews };
  }

  try {
    console.log("NewsLoader: Attempting to fetch news from API");

    // Use absolute URL with full path
    const apiUrl = "http://51.20.22.69:3000/api/articles";

    // Increased timeout and added more detailed error handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

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
    console.log(
      "NewsLoader: Response headers:",
      Object.fromEntries(response.headers.entries())
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error("NewsLoader: Error response text", errorText);
      throw new Error(`Could not fetch news: ${response.status} ${errorText}`);
    }

    const newsData = await response.json();

    console.log("NewsLoader: Fetched news data", newsData);

    if (!newsData || newsData.length === 0) {
      console.warn("NewsLoader: Received empty news data");
      toast.warn("No news found");
    } else {
      // Only cache if we have actual data
      cacheNewsData(newsData);
    }

    return { newsData };
  } catch (error) {
    console.error("NewsLoader: Detailed error", {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });

    // More specific error handling
    if (error.name === "AbortError") {
      toast.error("News fetch timed out");
    } else if (error.name === "TypeError") {
      toast.error("Network error. Check your connection.");
    } else {
      toast.error(`Failed to fetch news: ${error.message}`);
    }

    return { newsData: [] };
  }
}
