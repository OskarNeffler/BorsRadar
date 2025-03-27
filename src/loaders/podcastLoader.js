// src/loaders/podcastLoader.js
import { waait } from "../helpers";
import { toast } from "react-toastify";

export async function podcastLoader() {
  console.log("PodcastLoader: Starting loader function");

  // Lägg till en kort väntetid för laddningsanimation
  await waait(300);

  try {
    console.log("PodcastLoader: Attempting to fetch podcast data from API");

    // Använd din API-URL (justera efter behov)
    const apiUrl = "http://13.61.135.153:8000/";

    // Hantera timeout och mer detaljerad felhantering
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 sekunder timeout

    const response = await fetch(apiUrl, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    console.log("PodcastLoader: Response status", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("PodcastLoader: Error response text", errorText);
      throw new Error(
        `Kunde inte hämta podcast-data: ${response.status} ${errorText}`
      );
    }

    // Parsa respons-data
    const podcastData = await response.json();

    console.log("PodcastLoader: Fetched podcast data", podcastData);

    return { podcastData };
  } catch (error) {
    console.error("PodcastLoader: Detailed error", {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });

    // Mer specifik felhantering
    if (error.name === "AbortError") {
      toast.error("Podcast-hämtning timeout");
    } else if (error.name === "TypeError") {
      toast.error("Nätverksfel. Kontrollera din anslutning.");
    } else {
      toast.error(`Kunde inte hämta podcast-data: ${error.message}`);
    }

    return { podcastData: null, error: error.message };
  }
}
