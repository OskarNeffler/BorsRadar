import { waait } from "../helpers";
import { toast } from "react-toastify";
import { API_BASE_URL } from "../config";

export async function relatedContentLoader() {
  console.log("RelatedContentLoader: Starting loader function");

  // Lägg till en kort väntetid för laddningsanimation
  await waait(500);

  try {
    console.log("RelatedContentLoader: Attempting to fetch related content");

    // Använd din API-URL med korrekt basadress
    const apiUrl = `${API_BASE_URL}/content/topics`;

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

    console.log("RelatedContentLoader: Response status", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("RelatedContentLoader: Error response text", errorText);
      throw new Error(
        `Kunde inte hämta relaterat innehåll: ${response.status} ${errorText}`
      );
    }

    // Parsa respons-data
    const contentData = await response.json();

    console.log("RelatedContentLoader: Fetched related content", contentData);

    return { contentData };
  } catch (error) {
    console.error("RelatedContentLoader: Detailed error", {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });

    // Mer specifik felhantering
    if (error.name === "AbortError") {
      toast.error("Hämtning av relaterat innehåll timeout");
    } else if (error.name === "TypeError") {
      toast.error("Nätverksfel. Kontrollera din anslutning.");
    } else {
      toast.error(`Kunde inte hämta relaterat innehåll: ${error.message}`);
    }

    return { contentData: null, error: error.message };
  }
}
