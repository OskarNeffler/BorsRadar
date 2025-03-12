import { useLoaderData, useNavigation } from "react-router-dom";
import { useState } from "react";
import { toast } from "react-toastify";
import { formatDate, truncateText } from "../helpers";

const NewsPage = () => {
  const { newsData } = useLoaderData();
  const navigation = useNavigation();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await fetch("http://13.60.23.134/news/refresh");
      if (!response.ok) {
        throw new Error("Kunde inte uppdatera nyheter");
      }
      const result = await response.json();
      if (result.success) {
        const newsResponse = await fetch("http://13.60.23.134/news");
        if (!newsResponse.ok) {
          throw new Error("Kunde inte hämta nya nyheter");
        }
        const freshNewsData = await newsResponse.json();
        // Här behöver du hantera cachen via en funktion, t.ex. importera och anropa en funktion från helpers
        // Exempel: cacheNewsData(freshNewsData);
        window.location.reload();
        toast.success("Nyheterna har uppdaterats");
      } else {
        throw new Error("Kunde inte uppdatera nyheterna");
      }
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
                {article.image_url && (
                  <div
                    className="news-image"
                    style={{
                      backgroundImage: `url('${article.image_url.replace(
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
                    {formatDate(article.date)}
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
