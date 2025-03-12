// src/loaders/newsLoader.js
import { waait, cacheNewsData, getCachedNews } from "../helpers";
import { toast } from "react-toastify";

export async function newsLoader() {
  await waait(500);
  const cachedNews = getCachedNews();
  if (cachedNews) {
    return { newsData: cachedNews };
  }
  try {
    const response = await fetch("http://13.60.23.134/news");
    if (!response.ok) {
      throw new Error("Kunde inte hämta nyheter");
    }
    const newsData = await response.json();
    cacheNewsData(newsData);
    return { newsData };
  } catch (error) {
    toast.error("Fel vid hämtning av nyheter");
    return { newsData: [] };
  }
}
