export async function combinedDashboardLoader() {
  try {
    // Hämta nyhetsdata
    const newsResponse = await fetch(
      "http://51.20.22.69:3000/api/bors-nyheter"
    );

    // Hämta podcast-data
    const podcastResponse = await fetch("http://localhost:8000");

    if (!newsResponse.ok || !podcastResponse.ok) {
      throw new Error("Kunde inte hämta dashboard-data");
    }

    const newsData = await newsResponse.json();
    const podcastData = await podcastResponse.json();

    return {
      newsData: newsData.articles || [],
      podcastData,
    };
  } catch (error) {
    console.error("Dashboard loading error:", error);
    return {
      newsData: [],
      podcastData: {},
      error: error.message,
    };
  }
}
