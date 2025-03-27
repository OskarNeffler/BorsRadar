// src/pages/NewsPage.jsx
import { useLoaderData, useNavigation } from "react-router-dom";
import { useState } from "react";
import { toast } from "react-toastify";
import { formatDate, truncateText, cacheNewsData } from "../helpers";

const NewsPage = () => {
  const { newsData } = useLoaderData();
  const navigation = useNavigation();
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated] = useState(new Date());

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await fetch("http://13.61.135.153:8000/news-articles");
      if (!response.ok) {
        throw new Error("Kunde inte uppdatera nyheter");
      }

      const data = await response.json();

      // Mappa om artiklarna till det format som din frontend förväntar sig
      const articles = (data.news_articles || []).map((article) => ({
        id: article.id,
        title: article.title,
        summary: article.summary || "",
        url: article.url || "#",
        imageUrl: article.image_url || null,
        publishedAt: article.published_at,
        source: article.source || "Börsnyheter",
        content: article.content || "",
      }));

      cacheNewsData(articles);
      window.location.reload();
      toast.success("Nyheterna har uppdaterats");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setRefreshing(false);
    }
  };

  const isLoading = navigation.state === "loading" || refreshing;

  // Funktion för att skapa en bild-URL baserat på artikeldata
  const getImageUrl = (article) => {
    if (article.imageUrl) return article.imageUrl;

    // Om artikeln är från specifika källor, använd deras bild-URL-format
    if (article.url && article.url.includes("di.se")) {
      const articleId = article.url.split("/").pop().split("?")[0];
      return `https://images.di.se/api/v1/images/${articleId}?width=400&height=240&fit=crop`;
    }

    // Fallback placeholder
    return "https://via.placeholder.com/400x200?text=Börsradar";
  };

  return (
    <div className="grid-lg">
      <div
        className="flex-lg"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Börsnyheter</h1>
        <button
          onClick={handleRefresh}
          className="btn btn--dark"
          disabled={isLoading}
        >
          {isLoading ? "Uppdaterar..." : "Uppdatera nyheter"}
        </button>
      </div>

      <div className="grid-sm">
        <p>
          Senaste nyheterna från finansmarknaden.
          <small style={{ display: "block", marginTop: "5px" }}>
            Senast uppdaterad: {formatDate(lastUpdated)}
          </small>
        </p>
      </div>

      {isLoading ? (
        <div className="loading-spinner"></div>
      ) : newsData.length === 0 ? (
        <div className="grid-sm">
          <p>Inga nyheter kunde hämtas. Försök igen senare.</p>
        </div>
      ) : (
        <div className="news-container" style={{ width: "100%" }}>
          {newsData.map((article) => (
            <div key={article.id} className="news-item">
              <a
                href={article.url}
                className="news-link"
                target="_blank"
                rel="noopener noreferrer"
              >
                <div
                  className="news-image"
                  style={{
                    backgroundImage: `url(${getImageUrl(article)})`,
                  }}
                />
                <div className="news-content">
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "0.3rem",
                    }}
                  >
                    <span className="content-type-badge news">
                      {article.source || "Nyhet"}
                    </span>
                    <small style={{ color: "hsl(var(--muted))" }}>
                      {article.publishedAt
                        ? formatDate(article.publishedAt)
                        : "Nyligen publicerad"}
                    </small>
                  </div>
                  <h3 className="news-title">{article.title}</h3>
                  <p className="news-summary">
                    {truncateText(article.summary, 150)}
                  </p>
                </div>
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NewsPage;
