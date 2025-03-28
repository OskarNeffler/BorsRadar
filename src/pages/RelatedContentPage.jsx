// src/pages/RelatedContentPage.jsx
import { useState, useEffect } from "react";
import { useLoaderData, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { formatDate, truncateText } from "../helpers";
import { API_BASE_URL } from "../config";

const RelatedContentPage = () => {
  const initialData = useLoaderData();
  const [contentData, setContentData] = useState(
    initialData?.contentData || null
  );
  const [error, setError] = useState(initialData?.error || null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [companyGroups, setCompanyGroups] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [expandedItems, setExpandedItems] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDetailedContent = async (topicId) => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/content/topic/${topicId}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        if (!response.ok) {
          throw new Error(
            `Kunde inte hämta detaljerat innehåll: ${response.status}`
          );
        }

        const detailedData = await response.json();
        return detailedData;
      } catch (error) {
        console.error("Fel vid hämtning av detaljerat innehåll:", error);
        return null;
      }
    };

    const processTopics = async () => {
      if (contentData && contentData.trending_topics) {
        const processedGroups = await Promise.all(
          contentData.trending_topics.map(async (topic) => {
            const detailedContent = await fetchDetailedContent(topic.topic_id);

            return {
              ...topic,
              news: detailedContent?.news || [],
              podcasts: detailedContent?.podcasts || [],
              detailedContent: detailedContent,
            };
          })
        );

        setCompanyGroups(processedGroups);

        // Välj första ämnet automatiskt om det finns resultat
        if (processedGroups.length > 0 && !selectedCompany) {
          setSelectedCompany(processedGroups[0].topic);
        }
      }
    };

    processTopics();
  }, [contentData, selectedCompany]);

  const handleSearch = async (e) => {
    e.preventDefault();

    if (!searchQuery.trim()) {
      toast.info("Ange en sökfråga");
      return;
    }

    setIsSearching(true);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/content/search`, {
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

      setSearchResults({
        results: data.results || [],
        query: data.query,
      });

      setSelectedCompany(null);
      setError(null);
    } catch (err) {
      console.error("Sökfel:", err);
      toast.error(err.message);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/content`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Kunde inte uppdatera innehåll: ${response.status}`);
      }

      const freshData = await response.json();
      setContentData(freshData);
      setError(null);
      toast.success("Innehållet har uppdaterats");
    } catch (err) {
      toast.error(err.message);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const getActiveCompany = () => {
    if (selectedCompany && companyGroups.length > 0) {
      return companyGroups.find((c) => c.topic === selectedCompany);
    }
    return null;
  };

  const activeCompany = getActiveCompany();

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    setIsSearching(false);
    if (companyGroups.length > 0) {
      setSelectedCompany(companyGroups[0].topic);
    }
  };

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
            Innehållet grupperas automatiskt för att visa relaterat innehåll.
          </small>
        </p>
      </div>

      <div
        className="form-wrapper"
        style={{ maxWidth: "none", marginBottom: "2rem" }}
      >
        <form onSubmit={handleSearch} className="flex-md">
          <div style={{ flex: "1", position: "relative" }}>
            <span
              style={{
                position: "absolute",
                left: "0.75rem",
                top: "0.75rem",
                color: "hsl(var(--muted))",
              }}
            >
              🔍
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Sök efter ämnen, nyheter och podcasts..."
              disabled={isLoading}
              style={{ paddingLeft: "2.5rem" }}
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

      {isLoading ? (
        <div className="loading-spinner"></div>
      ) : error ? (
        <div className="form-wrapper" style={{ textAlign: "center" }}>
          <h2 className="h3" style={{ marginBottom: "1rem" }}>
            Något gick fel
          </h2>
          <p>{error}</p>
          <button
            className="btn btn--dark"
            style={{ margin: "1rem auto" }}
            onClick={handleRefresh}
          >
            Försök igen
          </button>
        </div>
      ) : isSearching && searchResults ? (
        <div className="form-wrapper">
          <h2>Sökresultat för "{searchQuery}"</h2>
          <div className="grid-sm">
            {searchResults.results?.length === 0 ? (
              <p>Inga resultat hittades för din sökning.</p>
            ) : (
              <div>
                <p>Hittade {searchResults.results?.length || 0} resultat</p>
                {/* Implementera detaljerad sökresultatvisning här */}
              </div>
            )}
          </div>
        </div>
      ) : companyGroups.length === 0 ? (
        <div className="form-wrapper" style={{ textAlign: "center" }}>
          <h2 className="h3">Inga ämnesgrupperingar hittades</h2>
          <p>Det finns för närvarande inga ämnesgrupperingar att visa.</p>
          <button
            className="btn btn--dark"
            style={{ margin: "1rem auto" }}
            onClick={handleRefresh}
          >
            Försök igen
          </button>
        </div>
      ) : (
        <div
          className="flex-lg"
          style={{ alignItems: "flex-start", gap: "2rem" }}
        >
          <div style={{ width: "250px", flexShrink: 0 }}>
            <div className="form-wrapper" style={{ padding: "1rem" }}>
              <h2 className="h3" style={{ marginBottom: "1rem" }}>
                Ämnen
              </h2>
              <div className="grid-xs">
                {companyGroups.map((topic) => (
                  <button
                    key={topic.topic}
                    className={`btn ${
                      selectedCompany === topic.topic
                        ? "btn--dark"
                        : "btn--outline"
                    }`}
                    onClick={() => setSelectedCompany(topic.topic)}
                    style={{ marginBottom: "0.5rem", textAlign: "left" }}
                  >
                    <div>
                      {topic.topic}
                      <small style={{ display: "block", fontSize: "0.8rem" }}>
                        {topic.item_count} innehåll
                      </small>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div style={{ flex: "1" }}>
            {activeCompany ? (
              <div className="form-wrapper">
                <h2 className="h2">{activeCompany.topic}</h2>

                <div style={{ marginBottom: "1.5rem" }}>
                  <p>{activeCompany.summary}</p>
                  <div style={{ marginTop: "0.5rem" }}>
                    <strong>Nyckelord:</strong>{" "}
                    {activeCompany.keywords?.join(", ") || "Inga nyckelord"}
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
                      {activeCompany.item_count || 0}
                    </strong>
                    <span>Totalt innehåll</span>
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
                      {activeCompany.topic_id || "N/A"}
                    </strong>
                    <span>Ämnes-ID</span>
                  </div>

                  <div
                    style={{
                      padding: "0.5rem 1rem",
                      backgroundColor: "hsl(40, 70%, 50%, 0.1)",
                      color: "hsl(40, 70%, 40%)",
                      borderRadius: "var(--round-md)",
                      fontSize: "0.9rem",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                    }}
                  >
                    <strong style={{ fontSize: "1.25rem" }}>
                      {activeCompany.sentiment !== undefined
                        ? activeCompany.sentiment
                        : 0}
                    </strong>
                    <span>Sentiment</span>
                  </div>
                </div>

                <div>
                  <h3>Nyheter</h3>
                  {activeCompany.news && activeCompany.news.length > 0 ? (
                    <div>
                      {activeCompany.news.map((newsItem) => (
                        <div
                          key={newsItem.id}
                          style={{
                            marginBottom: "1rem",
                            padding: "1rem",
                            border: "1px solid #eee",
                          }}
                        >
                          <h4>{newsItem.title}</h4>
                          <p>{newsItem.summary}</p>
                          <small>{formatDate(newsItem.published_at)}</small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>Inga nyheter hittades för detta ämne.</p>
                  )}

                  <h3>Podcasts</h3>
                  {activeCompany.podcasts &&
                  activeCompany.podcasts.length > 0 ? (
                    <div>
                      {activeCompany.podcasts.map((podcast) => (
                        <div
                          key={podcast.id}
                          style={{
                            marginBottom: "1rem",
                            padding: "1rem",
                            border: "1px solid #eee",
                          }}
                        >
                          <h4>{podcast.title}</h4>
                          <p>{podcast.summary}</p>
                          <small>{formatDate(podcast.published_at)}</small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>Inga podcasts hittades för detta ämne.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="grid-sm">
                <p>Välj ett ämne från listan för att se mer information.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RelatedContentPage;
