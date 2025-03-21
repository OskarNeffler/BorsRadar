import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Table from "../components/Table";
import Nav from "../components/Nav";

const PodcastPage = () => {
  const [podcasts, setPodcasts] = useState([]);
  const [stockMentions, setStockMentions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState("");
  const [stockList, setStockList] = useState([]);

  // Hämta podcasts från API
  const fetchPodcasts = async () => {
    try {
      setIsLoading(true);
      const response = await fetch("http://localhost:8000/podcasts");
      if (!response.ok) {
        throw new Error("Kunde inte hämta podcast-data");
      }
      const data = await response.json();
      setPodcasts(data.podcasts || []);

      // Extrahera alla unika aktienamn
      const allStocks = new Set();

      if (data.podcasts && data.podcasts.length > 0) {
        data.podcasts.forEach((podcast) => {
          podcast.episodes.forEach((episode) => {
            if (episode.stock_analysis && episode.stock_analysis.mentions) {
              episode.stock_analysis.mentions.forEach((mention) => {
                allStocks.add(mention.name);
              });
            }
          });
        });
      }

      setStockList(Array.from(allStocks).sort());
    } catch (err) {
      console.error("Fel vid hämtning av podcasts:", err);
      setError("Kunde inte hämta podcast-data. Försök igen senare.");
    } finally {
      setIsLoading(false);
    }
  };

  // Hämta aktieomtal för vald aktie
  const fetchStockMentions = async (stockName) => {
    if (!stockName) {
      setStockMentions([]);
      return;
    }

    try {
      setIsLoading(true);
      const response = await fetch(
        `http://localhost:8000/aktier?namn=${encodeURIComponent(stockName)}`
      );
      if (!response.ok) {
        throw new Error("Kunde inte hämta aktieomtal");
      }
      const data = await response.json();
      setStockMentions(data.mentions || []);
    } catch (err) {
      console.error("Fel vid hämtning av aktieomtal:", err);
      setError("Kunde inte hämta aktieomtal. Försök igen senare.");
    } finally {
      setIsLoading(false);
    }
  };

  // Ladda podcasts när komponenten laddas
  useEffect(() => {
    fetchPodcasts();
  }, []);

  // Uppdatera aktieomtal när vald aktie ändras
  useEffect(() => {
    if (selectedStock) {
      fetchStockMentions(selectedStock);
    }
  }, [selectedStock]);

  // Formatera podcast-data för tabellen
  const formatPodcastData = () => {
    const tableData = [];

    podcasts.forEach((podcast) => {
      podcast.episodes.forEach((episode) => {
        // Räkna antalet aktieomtal i avsnittet
        const mentionCount = episode.stock_analysis?.mentions?.length || 0;

        if (mentionCount > 0) {
          tableData.push({
            podcast: podcast.podcast_name,
            episode: episode.title,
            date: episode.date,
            mentions: mentionCount,
            sentiment: calculateAverageSentiment(
              episode.stock_analysis?.mentions
            ),
            link: episode.link,
          });
        }
      });
    });

    return tableData;
  };

  // Beräkna genomsnittligt sentiment för ett avsnitt
  const calculateAverageSentiment = (mentions) => {
    if (!mentions || mentions.length === 0) return "Neutral";

    const sentimentMap = {
      positivt: 1,
      neutralt: 0,
      negativt: -1,
    };

    let total = 0;
    mentions.forEach((mention) => {
      total += sentimentMap[mention.sentiment.toLowerCase()] || 0;
    });

    const average = total / mentions.length;

    if (average > 0.3) return "Positivt";
    if (average < -0.3) return "Negativt";
    return "Neutralt";
  };

  // Formatera aktieomtal för tabellen
  const formatStockMentionData = () => {
    return stockMentions.map((item) => ({
      podcast: item.podcast,
      episode: item.episode,
      date: item.date,
      context: item.mentions.map((m) => m.context).join(" | "),
      sentiment: calculateAverageSentiment(item.mentions),
      link: item.link,
    }));
  };

  // Kolumndefinitioner för podcast-tabellen
  const podcastColumns = [
    { header: "Podcast", accessor: "podcast" },
    { header: "Avsnitt", accessor: "episode" },
    { header: "Datum", accessor: "date" },
    { header: "Antal aktieomtal", accessor: "mentions" },
    {
      header: "Sentiment",
      accessor: "sentiment",
      cell: ({ value }) => (
        <span
          className={`font-semibold ${
            value === "Positivt"
              ? "text-green-600"
              : value === "Negativt"
              ? "text-red-600"
              : "text-gray-600"
          }`}
        >
          {value}
        </span>
      ),
    },
    {
      header: "Länk",
      accessor: "link",
      cell: ({ value }) => (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:underline"
        >
          Öppna ↗
        </a>
      ),
    },
  ];

  // Kolumndefinitioner för aktieomtal-tabellen
  const stockMentionColumns = [
    { header: "Podcast", accessor: "podcast" },
    { header: "Avsnitt", accessor: "episode" },
    { header: "Datum", accessor: "date" },
    { header: "Kontext", accessor: "context" },
    {
      header: "Sentiment",
      accessor: "sentiment",
      cell: ({ value }) => (
        <span
          className={`font-semibold ${
            value === "Positivt"
              ? "text-green-600"
              : value === "Negativt"
              ? "text-red-600"
              : "text-gray-600"
          }`}
        >
          {value}
        </span>
      ),
    },
    {
      header: "Länk",
      accessor: "link",
      cell: ({ value }) => (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:underline"
        >
          Öppna ↗
        </a>
      ),
    },
  ];

  return (
    <div className="container mx-auto p-4">
      <Nav />

      <h1 className="text-2xl font-bold mb-6">Podcasts</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Aktiefilter */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Filtrera på aktie
        </label>
        <div className="flex space-x-4">
          <select
            className="p-2 border rounded-md w-64"
            value={selectedStock}
            onChange={(e) => setSelectedStock(e.target.value)}
          >
            <option value="">Visa alla podcasts</option>
            {stockList.map((stock) => (
              <option key={stock} value={stock}>
                {stock}
              </option>
            ))}
          </select>

          {selectedStock && (
            <button
              className="bg-gray-200 hover:bg-gray-300 text-gray-800 py-2 px-4 rounded"
              onClick={() => setSelectedStock("")}
            >
              Rensa filter
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : selectedStock ? (
        // Visa aktieomtal för vald aktie
        <>
          <h2 className="text-xl font-semibold mb-4">
            Omnämnanden av {selectedStock}
          </h2>
          {stockMentions.length > 0 ? (
            <Table
              columns={stockMentionColumns}
              data={formatStockMentionData()}
            />
          ) : (
            <p className="text-gray-500">
              Inga omnämnanden hittades för {selectedStock}.
            </p>
          )}
        </>
      ) : (
        // Visa alla podcasts
        <>
          <h2 className="text-xl font-semibold mb-4">
            Alla podcast-avsnitt med aktieomtal
          </h2>
          {formatPodcastData().length > 0 ? (
            <Table columns={podcastColumns} data={formatPodcastData()} />
          ) : (
            <p className="text-gray-500">
              Inga podcast-avsnitt med aktieomtal hittades.
            </p>
          )}
        </>
      )}
    </div>
  );
};

export default PodcastPage;
