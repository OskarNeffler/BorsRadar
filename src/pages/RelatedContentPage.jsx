// src/pages/RelatedContentPage.jsx
import { useState, useEffect } from "react";
import { useLoaderData, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { formatDate, truncateText } from "../helpers";

const RelatedContentPage = () => {
  const { contentData, error: loaderError } = useLoaderData();
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(loaderError);
  const navigate = useNavigate();

  // Strukturera om data för enklare hantering
  const [formattedTopics, setFormattedTopics] = useState([]);

  useEffect(() => {
    if (contentData?.trending_topics) {
      const topics = contentData.trending_topics.map((topic) => {
        // Separera nyheter och podcasts för varje ämne
        const newsItems = [];
        const podcastItems = [];

        // Hämta totalt antal av varje typ
        let newsCount = 0;
        let podcastCount = 0;

        // Sentiment-analys
        let totalSentiment = 0;
        let sentimentCount = 0;

        for (const item of topic.items || []) {
          if (item.type === "news") {
            newsItems.push(item);
            newsCount++;

            // Beräkna sentiment om det finns
            if (typeof item.sentiment === "number") {
              totalSentiment += item.sentiment;
              sentimentCount++;
            }
          } else if (item.type === "podcast") {
            podcastItems.push(item);
            podcastCount++;
          }
        }

        // Beräkna genomsnittligt sentiment
        const avgSentiment =
          sentimentCount > 0 ? totalSentiment / sentimentCount : 0;

        return {
          ...topic,
          news_items: newsItems,
          podcast_items: podcastItems,
          news_count: newsCount,
          podcast_count: podcastCount,
          sentiment: avgSentiment,
        };
      });

      setFormattedTopics(topics);

      // Sätt första ämnet som aktivt automatiskt
      if (topics.length > 0 && !activeTopicId) {
        setActiveTopicId(topics[0].topic_id);
      }
    }
  }, [contentData, activeTopicId]);

  // Sök efter innehåll
  const handleSearch = async (e) => {
    e.preventDefault();

    if (!searchQuery.trim()) {
      toast.info("Ange en sökfråga");
      return;
    }

    setIsSearching(true);
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/content/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          content_type: "mixed",
          max_results: 15,
        }),
      });

      if (!response.ok) {
        throw new Error(`Sökningen misslyckades: ${response.status}`);
      }

      const data = await response.json();
      setSearchResults(data);
      setActiveTopicId(null);
    } catch (err) {
      console.error("Sökfel:", err);
      toast.error(err.message);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Rensa sökning och återgå till ämnen
  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    setIsSearching(false);
    if (formattedTopics.length > 0) {
      setActiveTopicId(formattedTopics[0].topic_id);
    }
  };

  // Uppdatera innehåll
  const handleRefresh = async () => {
    setIsLoading(true);
    try {
      navigate(".", { replace: true });
      toast.success("Innehållet har uppdaterats");
    } catch (err) {
      toast.error(err.message);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Om inga trender hittas
  if (!formattedTopics.length && !error) {
    return (
      <div className="grid-lg">
        <div
          className="flex-lg"
          style={{ justifyContent: "space-between", alignItems: "center" }}
        >
          <h1>Relaterat innehåll</h1>
          <button
            onClick={handleRefresh}
            className="btn btn--dark"
            disabled={isLoading}
          >
            {isLoading ? "Uppdaterar..." : "Uppdatera innehåll"}
          </button>
        </div>

        <div className="grid-sm">
          <p>Inga trender hittades. Försök att uppdatera innehållet.</p>
        </div>
      </div>
    );
  }

  // Om det är ett fel
  if (error) {
    return (
      <div className="grid-lg">
        <h1>Relaterat innehåll</h1>
        <div className="grid-sm">
          <p className="text-warning">{error}</p>
          <button onClick={handleRefresh} className="btn btn--dark">
            Försök igen
          </button>
        </div>
      </div>
    );
  }

  // Hjälpfunktion för att skapa en bild-URL från ett innehåll
  const getImageUrl = (item) => {
    // För nyheter
    if (item.type === "news" && item.url && item.url.includes("di.se")) {
      // Extrapolera möjlig bild-URL från DI-artikel
      const articleId = item.url.split("/").pop().split("?")[0];
      return `https://images.di.se/api/v1/images/${articleId}?width=400&height=240&fit=crop`;
    }

    // För podcasts med YouTube-URL
    if (
      item.type === "podcast" &&
      item.video_url &&
      item.video_url.includes("youtube.com")
    ) {
      const videoId = item.video_url.split("v=")[1]?.split("&")[0];
      if (videoId) {
        return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
      }
    }

    // Fallback placeholder
    return "https://via.placeholder.com/400x200?text=Börsradar";
  };

  // Få aktivt ämne
  const getActiveTopic = () => {
    if (searchResults) {
      return null; // Vi är i sökresultatläge
    }

    if (!formattedTopics.length || !activeTopicId) {
      return null;
    }

    return formattedTopics.find((topic) => topic.topic_id === activeTopicId);
  };

  const activeTopic = getActiveTopic();

  // Få alla innehållsobjekt från aktivt ämne eller sökresultat
  const getContentItems = () => {
    if (searchResults) {
      return searchResults.results.map((result) => result.content);
    }

    if (!activeTopic) {
      return [];
    }

    return [
      ...(activeTopic.news_items || []),
      ...(activeTopic.podcast_items || []),
    ];
  };

  const contentItems = getContentItems();

  return (
    <div className="grid-lg">
      <div
        className="flex-lg"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Relaterat innehåll</h1>
        <button
          onClick={handleRefresh}
          className="btn btn--dark"
          disabled={isLoading}
        >
          {isLoading ? "Uppdaterar..." : "Uppdatera innehåll"}
        </button>
      </div>

      <div className="grid-sm">
        <p>
          Se finansnyheter och podcasts om samma ämnen grupperade tillsammans.
          <small style={{ display: "block", marginTop: "5px" }}>
            Innehållet grupperas automatiskt med hjälp av AI.
          </small>
        </p>
      </div>

      {/* Sökfält */}
      <div
        className="form-wrapper"
        style={{ maxWidth: "none", marginBottom: "2rem" }}
      >
        <form onSubmit={handleSearch} className="flex-md">
          <div style={{ flex: "1" }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Sök efter nyheter och podcasts..."
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            className="btn btn--dark"
            disabled={isLoading || !searchQuery.trim()}
          >
            Sök
          </button>
          {isSearching && (
            <button
              type="button"
              className="btn btn--outline"
              onClick={clearSearch}
            >
              Rensa sökning
            </button>
          )}
        </form>
      </div>

      <div
        className="flex-lg"
        style={{ alignItems: "flex-start", gap: "2rem" }}
      >
        {/* Vänster sidofält med ämnen */}
        {!isSearching && (
          <div style={{ width: "250px", flexShrink: 0 }}>
            <div className="form-wrapper" style={{ padding: "1rem" }}>
              <h2 className="h3" style={{ marginBottom: "1rem" }}>
                Trendande Ämnen
              </h2>
              <div className="grid-xs">
                {formattedTopics.map((topic) => (
                  <button
                    key={topic.topic_id}
                    className={`btn ${
                      activeTopicId === topic.topic_id
                        ? "btn--dark"
                        : "btn--outline"
                    }`}
                    onClick={() => setActiveTopicId(topic.topic_id)}
                    style={{ marginBottom: "0.5rem", textAlign: "left" }}
                  >
                    <div>
                      {topic.topic}
                      <small style={{ display: "block", fontSize: "0.8rem" }}>
                        {topic.news_count + topic.podcast_count ||
                          topic.item_count ||
                          0}{" "}
                        artiklar/podcasts
                      </small>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Huvudinnehåll */}
        <div style={{ flex: "1" }}>
          {isSearching && searchResults ? (
            <div className="form-wrapper">
              <h2 className="h2">Sökresultat för "{searchQuery}"</h2>
              <div style={{ marginBottom: "1rem" }}>
                <p>Hittade {searchResults.results.length} resultat</p>
              </div>

              {searchResults.query_analysis && (
                <div
                  style={{
                    backgroundColor: "hsl(var(--accent) / 0.1)",
                    padding: "1rem",
                    borderRadius: "var(--round-md)",
                    marginBottom: "1.5rem",
                  }}
                >
                  <h3 className="h3">Tolkning av din sökning</h3>
                  <p>{searchResults.query_analysis.interpreted_as}</p>

                  {searchResults.query_analysis.suggested_topics?.length >
                    0 && (
                    <div style={{ marginTop: "0.5rem" }}>
                      <h4 style={{ fontSize: "1rem", marginBottom: "0.25rem" }}>
                        Relaterade ämnen:
                      </h4>
                      <div
                        style={{
                          display: "flex",
                          gap: "0.5rem",
                          flexWrap: "wrap",
                        }}
                      >
                        {searchResults.query_analysis.suggested_topics.map(
                          (topic, i) => (
                            <span
                              key={i}
                              style={{
                                background: "hsl(var(--accent) / 0.2)",
                                color: "hsl(var(--accent))",
                                padding: "0.25rem 0.5rem",
                                borderRadius: "var(--round-full)",
                                fontSize: "0.9rem",
                              }}
                            >
                              {topic}
                            </span>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="grid-sm">
                {searchResults.results.length === 0 ? (
                  <p>Inga resultat hittades för din sökning.</p>
                ) : (
                  <div className="news-container" style={{ width: "100%" }}>
                    {searchResults.results.map((result, index) => (
                      <div key={index} className="news-item">
                        <a
                          href={
                            result.content.url ||
                            result.content.video_url ||
                            "#"
                          }
                          className="news-link"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <div
                            className="news-image"
                            style={{
                              backgroundImage: `url(${getImageUrl(
                                result.content
                              )})`,
                            }}
                          />
                          <div className="news-content">
                            <span
                              style={{
                                display: "inline-block",
                                padding: "0.25rem 0.5rem",
                                fontSize: "0.75rem",
                                backgroundColor:
                                  result.content.type === "news"
                                    ? "hsl(var(--accent) / 0.2)"
                                    : "hsl(220, 60%, 50%, 0.2)",
                                color:
                                  result.content.type === "news"
                                    ? "hsl(var(--accent))"
                                    : "hsl(220, 60%, 50%)",
                                borderRadius: "var(--round-full)",
                                marginBottom: "0.5rem",
                              }}
                            >
                              {result.content.type === "news"
                                ? "Nyhet"
                                : "Podcast"}
                            </span>
                            <h3 className="news-title">
                              {result.content.title}
                            </h3>
                            <p className="news-summary">
                              {truncateText(
                                result.content.summary ||
                                  result.content.description ||
                                  result.match_reason ||
                                  "Ingen beskrivning tillgänglig",
                                150
                              )}
                            </p>
                            <small className="news-date">
                              {result.content.published_at
                                ? formatDate(result.content.published_at)
                                : "Nyligen publicerad"}
                            </small>
                          </div>
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : activeTopic ? (
            <div className="form-wrapper">
              <h2 className="h2">{activeTopic.topic}</h2>

              <div style={{ marginBottom: "1.5rem" }}>
                <p>{activeTopic.summary}</p>

                <div
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    flexWrap: "wrap",
                    marginTop: "1rem",
                  }}
                >
                  {activeTopic.keywords.map((keyword, i) => (
                    <span
                      key={i}
                      style={{
                        background: "hsl(var(--accent) / 0.2)",
                        color: "hsl(var(--accent))",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "var(--round-full)",
                        fontSize: "0.9rem",
                      }}
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "1rem",
                }}
              >
                <div
                  style={{
                    padding: "0.5rem 1rem",
                    backgroundColor: "hsl(var(--accent) / 0.1)",
                    color: "hsl(var(--accent))",
                    borderRadius: "var(--round-md)",
                    fontSize: "0.9rem",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                  }}
                >
                  <strong style={{ fontSize: "1.25rem" }}>
                    {activeTopic.news_count || 0}
                  </strong>
                  <span>Nyheter</span>
                </div>

                <div
                  style={{
                    padding: "0.5rem 1rem",
                    backgroundColor: "hsl(220, 60%, 50%, 0.1)",
                    color: "hsl(220, 60%, 50%)",
                    borderRadius: "var(--round-md)",
                    fontSize: "0.9rem",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                  }}
                >
                  <strong style={{ fontSize: "1.25rem" }}>
                    {activeTopic.podcast_count || 0}
                  </strong>
                  <span>Podcasts</span>
                </div>

                <div
                  style={{
                    padding: "0.5rem 1rem",
                    backgroundColor:
                      activeTopic.sentiment > 0.2
                        ? "hsl(150, 60%, 50%, 0.1)"
                        : activeTopic.sentiment < -0.2
                        ? "hsl(0, 60%, 50%, 0.1)"
                        : "hsl(40, 70%, 50%, 0.1)",
                    color:
                      activeTopic.sentiment > 0.2
                        ? "hsl(150, 60%, 40%)"
                        : activeTopic.sentiment < -0.2
                        ? "hsl(0, 60%, 40%)"
                        : "hsl(40, 70%, 40%)",
                    borderRadius: "var(--round-md)",
                    fontSize: "0.9rem",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                  }}
                >
                  <strong style={{ fontSize: "1.25rem" }}>
                    {activeTopic.sentiment > 0.2
                      ? "Positiv"
                      : activeTopic.sentiment < -0.2
                      ? "Negativ"
                      : "Neutral"}
                  </strong>
                  <span>Sentiment</span>
                </div>
              </div>

              <div className="news-container" style={{ width: "100%" }}>
                {contentItems.map((item, index) => (
                  <div key={index} className="news-item">
                    <a
                      href={item.url || item.video_url || "#"}
                      className="news-link"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <div
                        className="news-image"
                        style={{
                          backgroundImage: `url(${getImageUrl(item)})`,
                        }}
                      />
                      <div className="news-content">
                        <span
                          style={{
                            display: "inline-block",
                            padding: "0.25rem 0.5rem",
                            fontSize: "0.75rem",
                            backgroundColor:
                              item.type === "news"
                                ? "hsl(var(--accent) / 0.2)"
                                : "hsl(220, 60%, 50%, 0.2)",
                            color:
                              item.type === "news"
                                ? "hsl(var(--accent))"
                                : "hsl(220, 60%, 50%)",
                            borderRadius: "var(--round-full)",
                            marginBottom: "0.5rem",
                          }}
                        >
                          {item.type === "news" ? "Nyhet" : "Podcast"}
                        </span>
                        <h3 className="news-title">{item.title}</h3>
                        <p className="news-summary">
                          {truncateText(
                            item.summary ||
                              item.description ||
                              "Ingen beskrivning tillgänglig",
                            150
                          )}
                        </p>
                        <small className="news-date">
                          {item.published_at
                            ? formatDate(item.published_at)
                            : "Nyligen publicerad"}
                        </small>
                      </div>
                    </a>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid-sm">
              <p>Välj ett ämne från listan för att se relaterat innehåll.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RelatedContentPage;
