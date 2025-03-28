// src/components/PodcastDashboard.jsx
import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { toast } from "react-toastify";
import { formatDate } from "../helpers";

// Huvudkomponent för dashboarden
const PodcastDashboard = ({ initialData }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("podcast-avsnitt");
  const [selectedEpisode, setSelectedEpisode] = useState(null);
  const [lastUpdated] = useState(new Date());

  // Använd initialData från props om tillgänglig
  useEffect(() => {
    if (initialData) {
      console.log("Använder initialData från loader");
      setData(initialData);

      // Sätt första episoden som vald automatiskt om det finns episoder
      if (
        initialData.latest_podcast_episodes &&
        initialData.latest_podcast_episodes.length > 0
      ) {
        setSelectedEpisode(initialData.latest_podcast_episodes[0]);
      }

      setLoading(false);
      return;
    }

    // Om ingen initialData fanns, hämta från API
    const fetchPodcastData = async () => {
      try {
        setLoading(true);
        // Använd din faktiska backend-endpoint
        const response = await fetch("http://localhost:8000");

        if (!response.ok) {
          throw new Error(
            `Kunde inte hämta podcast-data: ${response.status} ${response.statusText}`
          );
        }

        const responseData = await response.json();
        console.log("Hämtad podcastdata:", responseData);
        setData(responseData);

        // Sätt första episoden som vald automatiskt om det finns episoder
        if (
          responseData.latest_podcast_episodes &&
          responseData.latest_podcast_episodes.length > 0
        ) {
          setSelectedEpisode(responseData.latest_podcast_episodes[0]);
        }

        setError(null);
      } catch (error) {
        console.error("Error fetching podcast data:", error);
        setError(
          "Kunde inte hämta podcast-data. Kontrollera API-anslutningen."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchPodcastData();
  }, [initialData]);

  // Hantera refresh - hämta ny data från API
  const handleRefresh = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://localhost:8000");
      if (!response.ok) {
        throw new Error(
          `Kunde inte uppdatera podcast-data: ${response.status} ${response.statusText}`
        );
      }

      const freshData = await response.json();
      setData(freshData);

      if (
        freshData.latest_podcast_episodes &&
        freshData.latest_podcast_episodes.length > 0
      ) {
        setSelectedEpisode(freshData.latest_podcast_episodes[0]);
      }

      toast.success("Podcast-datan har uppdaterats");
    } catch (error) {
      console.error("Fel vid uppdatering:", error);
      toast.error(error.message);
      setError("Kunde inte uppdatera podcast-data");
    } finally {
      setLoading(false);
    }
  };

  // Beräkna rekommendationsdata
  const prepareRecommendationData = (episodes) => {
    if (!episodes || episodes.length === 0) return [];

    const recommendationCounts = {
      buy: 0,
      hold: 0,
      sell: 0,
      none: 0,
    };

    episodes.forEach((episode) => {
      episode.stock_mentions.forEach((mention) => {
        const recommendation = mention.recommendation
          ? mention.recommendation.toLowerCase()
          : "none";

        if (recommendation.includes("köp") || recommendation.includes("buy")) {
          recommendationCounts.buy += 1;
        } else if (
          recommendation.includes("sälj") ||
          recommendation.includes("sell")
        ) {
          recommendationCounts.sell += 1;
        } else if (
          recommendation.includes("håll") ||
          recommendation.includes("hold")
        ) {
          recommendationCounts.hold += 1;
        } else {
          recommendationCounts.none += 1;
        }
      });
    });

    const total =
      recommendationCounts.buy +
      recommendationCounts.hold +
      recommendationCounts.sell +
      recommendationCounts.none;

    return [
      {
        name: "Ingen",
        value: recommendationCounts.none,
        percentage: Math.round((recommendationCounts.none / total) * 100),
      },
      {
        name: "Köp",
        value: recommendationCounts.buy,
        percentage: Math.round((recommendationCounts.buy / total) * 100),
      },
      {
        name: "Håll",
        value: recommendationCounts.hold,
        percentage: Math.round((recommendationCounts.hold / total) * 100),
      },
      {
        name: "Sälj",
        value: recommendationCounts.sell,
        percentage: Math.round((recommendationCounts.sell / total) * 100),
      },
    ];
  };

  // Gruppera företagsomtal för att visa vilka företag som nämns mest
  const prepareTopCompaniesMentioned = (episodes) => {
    if (!episodes || episodes.length === 0) return [];

    const companyCounts = {};

    episodes.forEach((episode) => {
      episode.stock_mentions.forEach((mention) => {
        const companyName = mention.name;
        if (!companyCounts[companyName]) {
          companyCounts[companyName] = {
            name: companyName,
            count: 0,
            ticker: mention.ticker || "-",
            positiveCount: 0,
            negativeCount: 0,
            neutralCount: 0,
          };
        }

        companyCounts[companyName].count += 1;

        const sentiment = mention.sentiment
          ? mention.sentiment.toLowerCase()
          : "";
        if (sentiment.includes("positiv")) {
          companyCounts[companyName].positiveCount += 1;
        } else if (sentiment.includes("negativ")) {
          companyCounts[companyName].negativeCount += 1;
        } else {
          companyCounts[companyName].neutralCount += 1;
        }
      });
    });

    return Object.values(companyCounts)
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  };

  // Hantera företagsomtal per podcast
  const preparePodcastMentionsData = (episodes) => {
    if (!episodes || episodes.length === 0) return [];

    return episodes
      .map((episode) => ({
        name:
          episode.title.length > 25
            ? episode.title.substring(0, 25) + "..."
            : episode.title,
        mentions: episode.stock_mentions.length,
      }))
      .sort((a, b) => b.mentions - a.mentions)
      .slice(0, 10);
  };

  // Färger för visualisering
  const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8"];
  const RECOMMENDATION_COLORS = {
    Ingen: "#4374E0",
    Köp: "#4DD187",
    Håll: "#FF9F40",
    Sälj: "#FF5C5C",
  };

  // Visa laddningsskärm
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  // Visa felmeddelande om något gick fel
  if (error && !data) {
    return (
      <div className="grid-sm">
        <div className="text-center text-warning">
          <h2 className="h3 mb-4">Ett fel uppstod</h2>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  // Om ingen data finns
  if (!data) {
    return (
      <div className="grid-sm">
        <p>Ingen podcast-data tillgänglig.</p>
      </div>
    );
  }

  // Förbered data för visualiseringar
  const topCompaniesMentioned =
    data && data.latest_podcast_episodes
      ? prepareTopCompaniesMentioned(data.latest_podcast_episodes)
      : [];

  const podcastMentionsData =
    data && data.latest_podcast_episodes
      ? preparePodcastMentionsData(data.latest_podcast_episodes)
      : [];

  const recommendationData =
    data && data.latest_podcast_episodes
      ? prepareRecommendationData(data.latest_podcast_episodes)
      : [];

  return (
    <div className="grid-lg">
      <div
        className="flex-lg"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <h1>Börsradar Podcast Dashboard</h1>
        <button
          onClick={handleRefresh}
          className="btn btn--dark"
          disabled={loading}
        >
          {loading ? "Uppdaterar..." : "Uppdatera data"}
        </button>
      </div>

      <div className="grid-sm">
        <p>
          Insikter från finanspoddar och aktiemarknaden
          <small style={{ display: "block", marginTop: "5px" }}>
            Senast uppdaterad: {formatDate(lastUpdated)}
          </small>
        </p>
      </div>

      {/* Dashboardens innehåll */}
      <div className="form-wrapper">
        {/* Flikar för olika delar av dashboarden */}
        <div
          className="flex-sm"
          style={{
            marginBottom: "1.5rem",
            borderBottom: "2px solid hsl(var(--light))",
          }}
        >
          <button
            className={`btn ${
              activeTab === "podcast-avsnitt" ? "btn--dark" : "btn--outline"
            }`}
            onClick={() => setActiveTab("podcast-avsnitt")}
          >
            Podcast-avsnitt
          </button>
          <button
            className={`btn ${
              activeTab === "marknadsanalys" ? "btn--dark" : "btn--outline"
            }`}
            onClick={() => setActiveTab("marknadsanalys")}
          >
            Marknadsanalys
          </button>
          <button
            className={`btn ${
              activeTab === "foretagsomtal" ? "btn--dark" : "btn--outline"
            }`}
            onClick={() => setActiveTab("foretagsomtal")}
          >
            Företagsomtal
          </button>
        </div>

        {/* Sammanfattningskort */}
        <div
          className="flex-md"
          style={{ justifyContent: "space-between", marginBottom: "1.5rem" }}
        >
          <div
            style={{
              padding: "1rem",
              background: "hsl(var(--bkg))",
              borderRadius: "var(--round-md)",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
              width: "32%",
            }}
          >
            <h3 className="h3">Podcastavsnitt</h3>
            <p
              style={{
                fontSize: "1.5rem",
                fontWeight: "bold",
                color: "hsl(var(--accent))",
              }}
            >
              {data.latest_podcast_episodes?.length || 0}
            </p>
          </div>
          <div
            style={{
              padding: "1rem",
              background: "hsl(var(--bkg))",
              borderRadius: "var(--round-md)",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
              width: "32%",
            }}
          >
            <h3 className="h3">Företagsomtal</h3>
            <p
              style={{
                fontSize: "1.5rem",
                fontWeight: "bold",
                color: "hsl(var(--accent))",
              }}
            >
              {data.summary?.total_stock_mentions ||
                data.latest_podcast_episodes?.reduce(
                  (sum, ep) => sum + ep.stock_mentions.length,
                  0
                ) ||
                0}
            </p>
          </div>
          <div
            style={{
              padding: "1rem",
              background: "hsl(var(--bkg))",
              borderRadius: "var(--round-md)",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
              width: "32%",
            }}
          >
            <h3 className="h3">Relaterade nyheter</h3>
            <p
              style={{
                fontSize: "1.5rem",
                fontWeight: "bold",
                color: "hsl(var(--accent))",
              }}
            >
              {data.summary?.total_related_news || 0}
            </p>
          </div>
        </div>

        {/* Podcast-avsnitt flik */}
        {activeTab === "podcast-avsnitt" && (
          <div className="grid-sm">
            <h2 className="h3" style={{ marginBottom: "1rem" }}>
              Senaste podcastavsnitt
            </h2>
            <div className="podcast-episode-list">
              {data.latest_podcast_episodes?.map((episode) => (
                <div
                  key={episode.id}
                  style={{
                    padding: "1rem",
                    borderBottom: "1px solid hsl(var(--light))",
                    cursor: "pointer",
                    background:
                      selectedEpisode?.id === episode.id
                        ? "hsl(var(--accent) / 0.1)"
                        : "hsl(var(--bkg))",
                    borderRadius: "var(--round-md)",
                    marginBottom: "0.5rem",
                  }}
                  onClick={() => setSelectedEpisode(episode)}
                >
                  <div
                    className="flex-sm"
                    style={{
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ flex: 1 }}>
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
                        background: "hsl(var(--accent) / 0.1)",
                        color: "hsl(var(--accent))",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "var(--round-full)",
                        fontSize: "var(--fs-200)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {episode.stock_mentions.length} företagsomtal
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Marknadsanalys flik */}
        {activeTab === "marknadsanalys" && (
          <div className="grid-md">
            <div
              className="flex-lg"
              style={{ alignItems: "stretch", marginBottom: "1.5rem" }}
            >
              {/* Företagsomtal per podcast */}
              <div
                style={{
                  flex: "0 0 48%",
                  background: "hsl(var(--bkg))",
                  borderRadius: "var(--round-md)",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                  padding: "1.5rem",
                }}
              >
                <h2 className="h3" style={{ marginBottom: "1rem" }}>
                  Företagsomtal per podcast
                </h2>
                <div style={{ height: "350px" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={podcastMentionsData}
                      margin={{ top: 20, right: 30, left: 20, bottom: 120 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        angle={-45}
                        textAnchor="end"
                        interval={0}
                        height={100}
                        tick={{ fontSize: 12 }} // Ändra 12 till önskad textstorlek
                      />

                      <YAxis
                        label={{
                          value: "Antal omnämnanden",
                          angle: -90,
                          position: "insideLeft",
                          fontSize: 12, // Ändra 12 till önskad textstorlek
                        }}
                        tick={{ fontSize: 12 }} // Ändra 12 till önskad textstorlek för skalmarkeringar
                      />
                      <Tooltip />
                      <Bar dataKey="mentions" fill="hsl(var(--accent))" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Rekommendationsfördelning */}
              <div
                style={{
                  flex: "0 0 48%",
                  background: "hsl(var(--bkg))",
                  borderRadius: "var(--round-md)",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                  padding: "1.5rem",
                }}
              >
                <h2 className="h3" style={{ marginBottom: "1rem" }}>
                  Rekommendationsfördelning
                </h2>
                <div style={{ height: "350px" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={recommendationData}
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        dataKey="value"
                        // Öka textstorleken här (t.ex. från 12 till 14 eller 16)
                        label={({ name, percent }) =>
                          `${(percent * 100).toFixed(0)}%`
                        }
                        labelStyle={{ fontSize: 14 }} // Lägg till denna rad eller öka värdet
                      >
                        {recommendationData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={
                              RECOMMENDATION_COLORS[entry.name] ||
                              COLORS[index % COLORS.length]
                            }
                          />
                        ))}
                      </Pie>
                      // För legendförklaringen under diagrammet
                      <Legend
                        formatter={(value, entry) => (
                          <span style={{ fontSize: 14 }}>{value}</span> // Öka värdet från t.ex. 12 till 14
                        )}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Företagsomtal flik */}
        {activeTab === "foretagsomtal" && (
          <div className="grid-sm">
            <h2 className="h3" style={{ marginBottom: "1rem" }}>
              Mest omnämnda företag
            </h2>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Företag</th>
                    <th>Ticker</th>
                    <th>Antal omnämnanden</th>
                    <th>Sentiment-fördelning</th>
                  </tr>
                </thead>
                <tbody>
                  {topCompaniesMentioned.map((company, index) => (
                    <tr key={index}>
                      <td style={{ fontWeight: "500" }}>{company.name}</td>
                      <td style={{ color: "hsl(var(--muted))" }}>
                        {company.ticker || "-"}
                      </td>
                      <td>{company.count}</td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            gap: "0.5rem",
                            justifyContent: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          {company.positiveCount > 0 && (
                            <span
                              style={{
                                padding: "0.25rem 0.5rem",
                                fontSize: "var(--fs-200)",
                                background: "hsl(150, 60%, 90%)",
                                color: "hsl(150, 60%, 30%)",
                                borderRadius: "var(--round-full)",
                              }}
                            >
                              {company.positiveCount} positiva
                            </span>
                          )}
                          {company.negativeCount > 0 && (
                            <span
                              style={{
                                padding: "0.25rem 0.5rem",
                                fontSize: "var(--fs-200)",
                                background: "hsl(0, 60%, 90%)",
                                color: "hsl(0, 60%, 35%)",
                                borderRadius: "var(--round-full)",
                              }}
                            >
                              {company.negativeCount} negativa
                            </span>
                          )}
                          {company.neutralCount > 0 && (
                            <span
                              style={{
                                padding: "0.25rem 0.5rem",
                                fontSize: "var(--fs-200)",
                                background: "hsl(var(--light))",
                                color: "hsl(var(--muted))",
                                borderRadius: "var(--round-full)",
                              }}
                            >
                              {company.neutralCount} neutrala
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Detaljerad information om det valda företaget */}
            {selectedEpisode && (
              <div style={{ marginTop: "2rem" }}>
                <h2 className="h3">
                  Detaljerad information om valda omnämnanden
                </h2>

                <div className="table">
                  <table>
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
                      {selectedEpisode.stock_mentions.map((mention, index) => (
                        <tr key={index}>
                          <td style={{ fontWeight: "500" }}>{mention.name}</td>
                          <td>{mention.ticker || "-"}</td>
                          <td>
                            <span
                              style={{
                                padding: "0.25rem 0.5rem",
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
                                  padding: "0.25rem 0.5rem",
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
                          <td
                            style={{
                              fontSize: "var(--fs-200)",
                              maxWidth: "300px",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {mention.context || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PodcastDashboard;
