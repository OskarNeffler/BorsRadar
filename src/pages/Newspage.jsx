import { useLoaderData, useNavigation } from "react-router-dom";
import { useState } from "react";
import { toast } from "react-toastify";
import { formatDate, truncateText, cacheNewsData } from "../helpers";

const NewsPage = () => {
  const { newsData } = useLoaderData();
  const navigation = useNavigation();
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated] = useState(new Date());
  // I NewsPage.jsx, lägg till detta för att inspektera datan
  console.log("Nyhetsdatan:", newsData);
  // Kontrollera specifikt om publishedAt finns
  console.log("Första artikelns publishedAt:", newsData[0]?.publishedAt);
  // Kontrollera specifikt om imageUrl finns
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await fetch("http://51.20.22.69:3000/api/articles");
      if (!response.ok) {
        throw new Error("Kunde inte uppdatera nyheter");
      }

      const freshNewsData = await response.json();
      cacheNewsData(freshNewsData);
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
          {newsData.map((article, index) => (
            <div key={index} className="news-item">
              <a
                href={article.url}
                className="news-link"
                target="_blank"
                rel="noopener noreferrer"
              >
                {article.imageUrl && (
                  <div
                    className="news-image"
                    style={{
                      backgroundImage: `url('${article.imageUrl.replace(
                        "&width=90&quality=70",
                        "&width=400&quality=80"
                      )}')`,
                    }}
                  />
                )}
                <div className="news-content">
                  <h3 className="news-title">{article.title}</h3>
                  <p className="news-summary">
                    {truncateText(article.summary, 150)}
                  </p>
                  <small className="news-date">
                    {(() => {
                      console.log(
                        `Artikel "${article.title}": publishedAt =`,
                        article.publishedAt
                      );
                      return article.publishedAt
                        ? formatDate(article.publishedAt)
                        : "Nyligen publicerad";
                    })()}
                  </small>
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
