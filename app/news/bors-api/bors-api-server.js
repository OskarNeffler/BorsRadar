// bors-api-server.js - Server för börsnyhet-API (ingen inloggning krävs)
// Detta API exponerar börsnyheter för din frontend

// Ladda konfiguration från .env
require("dotenv").config({ path: "../.env" });

const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const { logger } = require("../delade/logger");

// Skapa Express-app
const app = express();
const PORT = process.env.BORS_API_PORT || 3000;

// CORS-konfiguration
app.use(
  cors({
    origin: "*",
    methods: ["GET", "POST"],
    allowedHeaders: ["Content-Type", "Authorization"],
    credentials: true,
  })
);

app.use(express.json());

// Skapa mapp för sparad data om den inte finns
const DATA_DIR = path.join(__dirname, "data");
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Skapa mapp för loggar om den inte finns
const LOG_DIR = path.join(__dirname, "logs");
if (!fs.existsSync(LOG_DIR)) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

// Filsökväg för att spara börsnyheter
const STOCK_NEWS_FILE = path.join(DATA_DIR, "bors-nyheter.json");

// Läs in tidigare sparade börsnyheter om de finns
let stockNewsArticles = [];
if (fs.existsSync(STOCK_NEWS_FILE)) {
  try {
    const stockNewsData = fs.readFileSync(STOCK_NEWS_FILE, "utf8");
    stockNewsArticles = JSON.parse(stockNewsData);
    logger.info(
      `Läste in ${stockNewsArticles.length} tidigare sparade börsnyheter`
    );
  } catch (error) {
    logger.error("Fel vid inläsning av sparade börsnyheter:", error);
  }
}

// API-endpoints
// Hämta senaste börsnyheter med paginering
app.get("/api/bors-nyheter", (req, res) => {
  try {
    const { limit = 20, offset = 0 } = req.query;
    const limitNum = parseInt(limit, 10);
    const offsetNum = parseInt(offset, 10);

    const paginatedArticles = stockNewsArticles.slice(
      offsetNum,
      offsetNum + limitNum
    );

    res.json({
      total: stockNewsArticles.length,
      offset: offsetNum,
      limit: limitNum,
      articles: paginatedArticles,
    });
  } catch (error) {
    logger.error("Fel vid hämtning av börsnyheter:", error);
    res.status(500).json({ error: error.message });
  }
});

// Hämta en specifik artikel med ID eller URL
app.get("/api/bors-nyheter/:identifier", (req, res) => {
  try {
    const { identifier } = req.params;
    let article;

    // Kontrollera om identifier är ett index eller en URL
    if (!isNaN(identifier)) {
      // Om det är ett index/id
      const index = parseInt(identifier, 10);
      article = stockNewsArticles[index];
    } else {
      // Om det är en URL (eller del av URL)
      article = stockNewsArticles.find((a) => a.url.includes(identifier));
    }

    if (!article) {
      return res.status(404).json({ error: "Artikel hittades inte" });
    }

    res.json(article);
  } catch (error) {
    logger.error("Fel vid hämtning av specifik börsnyhet:", error);
    res.status(500).json({ error: error.message });
  }
});

// Hälsokontroll för att verifiera att servern körs
app.get("/health", (req, res) => {
  res.status(200).json({
    status: "UP",
    timestamp: new Date(),
    articleCount: stockNewsArticles.length,
    message: "Börs-API körs",
  });
});

// Manuell triggering av scraping
app.get("/api/trigger-scraping", (req, res) => {
  // Vi använder inte detta direkt, eftersom scraping sker via crontab
  // Men detta API kan användas för att verifiera att systemet fungerar
  res.json({
    message:
      "Scraping körs automatiskt var " +
      (process.env.BORS_SCRAPING_INTERVAL || 30) +
      " minut via crontab",
    lastUpdate:
      stockNewsArticles.length > 0
        ? new Date(stockNewsArticles[0].scrapedAt)
        : null,
    articleCount: stockNewsArticles.length,
  });
});

// Starta servern
app.listen(PORT, "0.0.0.0", () => {
  logger.info(`Börs-API server körs på port ${PORT}`);
  logger.info(`Hälsokontroll: http://[51.20.22.69]:${PORT}/health`);
  logger.info(`Börsnyheter API: http://[51.20.22.69]:${PORT}/api/bors-nyheter`);
});

// Exportera för användning i andra filer om det behövs
module.exports = {
  app,
  stockNewsArticles,
};
