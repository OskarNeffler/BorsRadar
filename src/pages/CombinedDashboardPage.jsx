// src/pages/CombinedDashboardPage.jsx
import { useState, useEffect } from "react";
import { useLoaderData, useNavigation } from "react-router-dom";
import { toast } from "react-toastify";
import { formatDate, truncateText } from "../helpers";
import {
  FaNewspaper,
  FaPodcast,
  FaChevronDown,
  FaChevronUp,
} from "react-icons/fa";

const CombinedDashboardPage = () => {
  // Fetch data from both loaders
  const { newsData, podcastData, error: loaderError } = useLoaderData();
  const navigation = useNavigation();
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated] = useState(new Date());
  const [selectedEpisode, setSelectedEpisode] = useState(null);
  const [expandedEpisodes, setExpandedEpisodes] = useState({});

  // Helpers for expanded content
  const toggleExpand = (episodeId) => {
    setExpandedEpisodes({
      ...expandedEpisodes,
      [episodeId]: !expandedEpisodes[episodeId],
    });
  };

  const isExpanded = (episodeId) => expandedEpisodes[episodeId] === true;

  // Set first episode as default selected if available
  useEffect(() => {
    if (podcastData?.latest_podcast_episodes?.length > 0 && !selectedEpisode) {
      setSelectedEpisode(podcastData.latest_podcast_episodes[0]);
    }
  }, [podcastData, selectedEpisode]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      // You would implement the actual refresh logic here
      toast.success("Dashboard har uppdaterats");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setRefreshing(false);
    }
  };

  const isLoading = navigation.state === "loading" || refreshing;

  // Function to create image URL based on article data
  const getImageUrl = (article) => {
    if (article.imageUrl) return article.imageUrl;

    if (article.url && article.url.includes("di.se")) {
      const articleId = article.url.split("/").pop().split("?")[0];
      return `https://images.di.se/api/v1/images/${articleId}?width=400&height=240&fit=crop`;
    }

    return null;
  };

  return (
    <div className="grid-lg">
      <div
        className="flex-lg"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Börsradar Dashboard</h1>
        <button
          onClick={handleRefresh}
          className="btn btn--dark"
          disabled={isLoading}
        >
          {isLoading ? "Uppdaterar..." : "Uppdatera dashboard"}
        </button>
      </div>

      <div className="grid-sm">
        <p>
          En översikt över senaste finansnyheter och podcasts
          <small style={{ display: "block", marginTop: "5px" }}>
            Senast uppdaterad: {formatDate(lastUpdated)}
          </small>
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="dashboard-overview">
        <div className="dashboard-card">
          <h3 className="h3">Podcastavsnitt</h3>
          <div className="dashboard-card-value">
            {podcastData?.latest_podcast_episodes?.length || 0}
          </div>
          <p>Senaste poddavsnitt</p>
        </div>

        <div className="dashboard-card">
          <h3 className="h3">Totala omnämnanden</h3>
          <div className="dashboard-card-value">
            {podcastData?.latest_podcast_episodes?.reduce(
              (sum, ep) => sum + (ep.stock_mentions?.length || 0),
              0
            ) || 0}
          </div>
          <p>Företagsomtal i podcasts</p>
        </div>

        <div className="dashboard-card">
          <h3 className="h3">Nyheter</h3>
          <div className="dashboard-card-value">{newsData?.length || 0}</div>
          <p>Senaste finansnyheter</p>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-spinner"></div>
      ) : loaderError ? (
        <div className="grid-sm">
          <p className="text-warning">{loaderError}</p>
        </div>
      ) : (
        <div className="combined-dashboard">
          {/* Podcasts Section */}
          <div className="dashboard-section">
            <h2>Senaste Podcasts</h2>

            <div className="podcast-episode-list">
              {podcastData?.latest_podcast_episodes?.map((episode) => (
                <div
                  key={episode.id}
                  className={`podcast-episode-card ${
                    selectedEpisode?.id === episode.id ? "active" : ""
                  }`}
                  onClick={() => setSelectedEpisode(episode)}
                >
                  <div
                    className="flex-sm"
                    style={{
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <div>
                      <h3
                        style={{ fontSize: "var(--fs-300)", fontWeight: "500" }}
                      >
                        {episode.title}
                      </h3>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "var(--fs-200)",
                          color: "hsl(var(--muted))",
                          marginTop: "0.25rem",
                        }}
                      >
                        <span>{episode.podcast_name || "Börssnurr"}</span>
                        <span>{formatDate(episode.published_at)}</span>
                      </div>
                    </div>
                    <div
                      style={{
                        padding: "0.25rem 0.5rem",
                        borderRadius: "var(--round-full)",
                        fontSize: "var(--fs-200)",
                        whiteSpace: "nowrap",
                        background: "hsl(var(--accent) / 0.1)",
                        color: "hsl(var(--accent))",
                      }}
                    >
                      {episode.stock_mentions?.length || 0} företagsomtal
                    </div>
                  </div>

                  {/* Expandable Summary */}
                  <button
                    className={`expand-button ${
                      isExpanded(episode.id) ? "expanded" : ""
                    }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(episode.id);
                    }}
                  >
                    {isExpanded(episode.id)
                      ? "Dölj sammanfattning"
                      : "Visa sammanfattning"}
                    {isExpanded(episode.id) ? (
                      <FaChevronUp />
                    ) : (
                      <FaChevronDown />
                    )}
                  </button>

                  <div
                    className={`expandable-content ${
                      isExpanded(episode.id) ? "expanded" : ""
                    }`}
                  >
                    <div className="podcast-summary">
                      <p>
                        {episode.summary || "Ingen sammanfattning tillgänglig."}
                      </p>

                      <div style={{ marginTop: "0.5rem" }}>
                        <h4
                          style={{
                            fontSize: "var(--fs-200)",
                            fontWeight: "500",
                          }}
                        >
                          Företag som nämns:
                        </h4>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "0.5rem",
                            marginTop: "0.25rem",
                          }}
                        >
                          {episode.stock_mentions?.map((mention, i) => (
                            <span
                              key={i}
                              style={{
                                padding: "0.1rem 0.5rem",
                                fontSize: "var(--fs-200)",
                                borderRadius: "var(--round-full)",
                                background:
                                  mention.sentiment === "positive" ||
                                  mention.sentiment?.includes("positiv")
                                    ? "hsl(150, 60%, 90%)"
                                    : mention.sentiment === "negative" ||
                                      mention.sentiment?.includes("negativ")
                                    ? "hsl(0, 60%, 90%)"
                                    : "hsl(var(--light))",
                                color:
                                  mention.sentiment === "positive" ||
                                  mention.sentiment?.includes("positiv")
                                    ? "hsl(150, 60%, 30%)"
                                    : mention.sentiment === "negative" ||
                                      mention.sentiment?.includes("negativ")
                                    ? "hsl(0, 60%, 35%)"
                                    : "hsl(var(--muted))",
                              }}
                            >
                              {mention.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* News Section */}
          <div className="dashboard-section">
            <h2>Senaste Nyheter</h2>

            <div
              className="news-container"
              style={{ gridTemplateColumns: "1fr" }}
            >
              {newsData?.slice(0, 5)?.map((article) => (
                <div key={article.id} className="news-item">
                  <a
                    href={article.url}
                    className="news-link"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {getImageUrl(article) ? (
                      <div
                        className="news-image"
                        style={{
                          backgroundImage: `url(${getImageUrl(article)})`,
                          height: "100px",
                        }}
                      />
                    ) : (
                      <div
                        className="news-image news-image-placeholder"
                        style={{ height: "100px" }}
                      >
                        <FaNewspaper size={24} />
                      </div>
                    )}
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
                    </div>
                  </a>
                </div>
              ))}
            </div>

            <div style={{ textAlign: "center", marginTop: "1rem" }}>
              <a href="/news" className="btn btn--outline">
                Visa alla nyheter
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Selected Episode Details */}
      {selectedEpisode && (
        <div className="dashboard-section" style={{ marginTop: "1.5rem" }}>
          <h2>Företagsomtal i "{selectedEpisode.title}"</h2>

          <div className="table-container">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Företag</th>
                  <th>Ticker</th>
                  <th>Sentiment</th>
                  <th>Rekommendation</th>
                  <th>Kontext</th>
                </tr>
              </thead>
              <tbody>
                {selectedEpisode.stock_mentions?.map((mention, index) => (
                  <tr key={index}>
                    <td style={{ fontWeight: "500" }}>{mention.name}</td>
                    <td>{mention.ticker || "-"}</td>
                    <td>
                      <span
                        style={{
                          padding: "0.15rem 0.4rem",
                          borderRadius: "var(--round-full)",
                          display: "inline-block",
                          fontSize: "var(--fs-200)",
                          background:
                            mention.sentiment === "positive" ||
                            mention.sentiment?.includes("positiv")
                              ? "hsl(150, 60%, 90%)"
                              : mention.sentiment === "negative" ||
                                mention.sentiment?.includes("negativ")
                              ? "hsl(0, 60%, 90%)"
                              : "hsl(var(--light))",
                          color:
                            mention.sentiment === "positive" ||
                            mention.sentiment?.includes("positiv")
                              ? "hsl(150, 60%, 30%)"
                              : mention.sentiment === "negative" ||
                                mention.sentiment?.includes("negativ")
                              ? "hsl(0, 60%, 35%)"
                              : "hsl(var(--muted))",
                        }}
                      >
                        {mention.sentiment || "Neutral"}
                      </span>
                    </td>
                    <td>
                      {mention.recommendation &&
                      mention.recommendation !== "none" ? (
                        <span
                          style={{
                            padding: "0.15rem 0.4rem",
                            borderRadius: "var(--round-full)",
                            display: "inline-block",
                            fontSize: "var(--fs-200)",
                            background:
                              mention.recommendation === "buy" ||
                              mention.recommendation?.includes("köp")
                                ? "hsl(150, 60%, 90%)"
                                : mention.recommendation === "sell" ||
                                  mention.recommendation?.includes("sälj")
                                ? "hsl(0, 60%, 90%)"
                                : "hsl(40, 70%, 90%)",
                            color:
                              mention.recommendation === "buy" ||
                              mention.recommendation?.includes("köp")
                                ? "hsl(150, 60%, 30%)"
                                : mention.recommendation === "sell" ||
                                  mention.recommendation?.includes("sälj")
                                ? "hsl(0, 60%, 35%)"
                                : "hsl(40, 70%, 30%)",
                          }}
                        >
                          {mention.recommendation}
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="context-cell">{mention.context || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default CombinedDashboardPage;
