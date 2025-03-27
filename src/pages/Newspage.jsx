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
      const response = await fetch("http://51.20.22.69:3000/api/bors-nyheter");
      if (!response.ok) {
        throw new Error("Kunde inte uppdatera nyheter");
      }

      const freshNewsData = await response.json();
      // freshNewsData = { total, offset, limit, articles: [...] }
      cacheNewsData(freshNewsData.articles || []);
      window.location.reload();
      toast.success("Nyheterna har uppdaterats");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setRefreshing(false);
    }
  };

  const isLoading = navigation.state === "loading" || refreshing;

  return (
    <div className="grid-lg">
      <div
        className="flex-lg"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Börsnyheter från Dagens Industri</h1>
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
          Senaste nyheterna från finansmarknaden, direkt från Dagens Industri.
          <small style={{ display: "block", marginTop: "5px" }}>
            Senast uppdaterad: {formatDate(lastUpdated)}
          </small>
        </p>
      </div>

      {isLoading ? (
        <div className="grid-sm">
          <p>Laddar nyheter...</p>
        </div>
      ) : newsData.length === 0 ? (
        <div className="grid-sm">
          <p>Inga nyheter kunde hämtas. Försök igen senare.</p>
        </div>
      ) : (
        <div className="news-container">
          {newsData.map((article, index) => {
            // Byt ut &width=90&quality=70 mot en större variant
            const biggerImageUrl = article.imageUrl
              ? article.imageUrl.replace(
                  "&width=90&quality=70",
                  "&width=400&quality=80"
                )
              : null;

            return (
              <div key={index} className="news-item">
                <a
                  href={article.url}
                  className="news-link"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {/* Visa endast <img> om vi har en bild-URL */}
                  {biggerImageUrl && (
                    <img
                      src={biggerImageUrl}
                      alt={article.title}
                      className="news-image-tag"
                    />
                  )}
                  <div className="news-content">
                    <h3 className="news-title">{article.title}</h3>
                    <p className="news-summary">
                      {truncateText(article.summary, 150)}
                    </p>
                    <small className="news-date">
                      {article.publishedAt
                        ? formatDate(article.publishedAt)
                        : "Nyligen publicerad"}
                    </small>
                  </div>
                </a>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default NewsPage;
