// di-scraper.js - Scraper med schemaläggning och förbättrad CORS

// Importera nödvändiga paket
const express = require("express");
const axios = require("axios");
const cheerio = require("cheerio");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const cron = require("node-cron");

// Skapa Express-app
const app = express();
const PORT = process.env.PORT || 3000;

// Aktivera CORS för alla ursprung (origins)
app.use(
  cors({
    origin: "*", // Tillåt alla ursprung
    methods: ["GET", "POST"], // Tillåtna metoder
    allowedHeaders: ["Content-Type", "Authorization"],
    credentials: true,
  })
);

app.use(express.json());

// Skapa mapp för sparad data om den inte finns
const DATA_DIR = path.join(__dirname, "data");
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR);
}

// Filsökväg för att spara artiklar
const ARTICLES_FILE = path.join(DATA_DIR, "di_articles.json");

// Läs in tidigare sparade artiklar om de finns
let scrapedArticles = [];
if (fs.existsSync(ARTICLES_FILE)) {
  try {
    const articlesData = fs.readFileSync(ARTICLES_FILE, "utf8");
    scrapedArticles = JSON.parse(articlesData);
    console.log(`Läste in ${scrapedArticles.length} tidigare sparade artiklar`);
  } catch (error) {
    console.error("Fel vid inläsning av sparade artiklar:", error);
  }
}

// Skapa en uppslagstabell för URL:er som vi redan har skrapat
const processedUrls = new Set(scrapedArticles.map((article) => article.url));

// Spara artiklar till fil
function saveArticlesToFile() {
  try {
    fs.writeFileSync(
      ARTICLES_FILE,
      JSON.stringify(scrapedArticles, null, 2),
      "utf8"
    );
    console.log(`Sparade ${scrapedArticles.length} artiklar till fil`);
  } catch (error) {
    console.error("Fel vid sparande av artiklar till fil:", error);
  }
}

// URLs för scraping
const DI_BASE_URL = "https://www.di.se";
const DI_NEWS_URL = "https://www.di.se/bors/nyheter/";

// Funktion för att scrapa artikellistan från DI
async function scrapeDiArticleList() {
  try {
    console.log(`Hämtar artiklar från ${DI_NEWS_URL}`);

    const response = await axios.get(DI_NEWS_URL);
    const $ = cheerio.load(response.data);
    const articles = [];

    // Hitta alla artikelelement
    $("article.news-item").each((index, element) => {
      // Hämta länk till artikeln
      const linkElement = $(element).find("a").first();
      const relativeUrl = linkElement.attr("href");
      const url = relativeUrl.startsWith("/")
        ? `${DI_BASE_URL}${relativeUrl}`
        : relativeUrl;

      // Kontrollera om vi redan har denna URL
      if (processedUrls.has(url)) {
        console.log(`Hoppar över redan processad artikel: ${url}`);
        return; // Skippa denna artikel
      }

      // Hämta titel
      const title = $(element).find(".news-item__heading").text().trim();

      // Hämta sammanfattning
      const summary = $(element).find(".news-item__text").text().trim();

      // Hämta bild-URL om den finns
      let imageUrl = null;
      const imgElement = $(element).find(".image__el");
      if (imgElement.length > 0) {
        imageUrl = imgElement.attr("src") || imgElement.attr("data-src");
      }

      if (title && url) {
        articles.push({
          title,
          url,
          summary,
          imageUrl,
          source: "di",
          publishedAt: new Date(), // Platshållare, kommer uppdateras när vi läser artikeln
          content: null, // Platshållare, kommer uppdateras när vi läser artikeln
        });
      }
    });

    console.log(`Hittade ${articles.length} nya artiklar`);
    return articles;
  } catch (error) {
    console.error(`Fel vid scraping av artikellista:`, error.message);
    return [];
  }
}

// Funktion för att scrapa fullständig artikel från DI
async function scrapeDiArticleContent(url) {
  try {
    console.log(`Hämtar artikelinnehåll från ${url}`);

    const response = await axios.get(url);
    const $ = cheerio.load(response.data);

    // Försök hitta publiceringstidpunkt
    let publishedAt = null;
    const timeElement = $("time.publication__time");
    if (timeElement.length) {
      const dateTimeStr = timeElement.attr("datetime");
      if (dateTimeStr) {
        publishedAt = new Date(dateTimeStr);
      }
    }

    // Hämta artikelinnehåll (sätt ihop alla stycken)
    let content = "";
    $(".article__body p").each((i, el) => {
      content += $(el).text() + "\n\n";
    });

    return {
      content: content.trim(),
      publishedAt,
    };
  } catch (error) {
    console.error(`Fel vid scraping av artikelinnehåll:`, error.message);
    return {
      content: null,
      publishedAt: null,
    };
  }
}

// Huvudfunktion för att scrapa
async function scrapeAll(limit = 15) {
  try {
    console.log(
      `[${new Date().toLocaleString()}] Startar schemalagd scraping...`
    );

    // Steg 1: Hämta alla artiklar från listan
    const newArticles = await scrapeDiArticleList();

    // Om inga nya artiklar hittades, avsluta
    if (newArticles.length === 0) {
      console.log("Inga nya artiklar hittades.");
      return {
        newArticles: 0,
        totalStored: scrapedArticles.length,
      };
    }

    // Steg 2: Hämta artikelinnehåll för nya artiklar (max "limit" stycken)
    const articlesToProcess = newArticles.slice(0, limit);
    const completeArticles = [];

    for (const article of articlesToProcess) {
      // Vänta lite mellan varje anrop för att inte överbelasta servern
      await new Promise((resolve) => setTimeout(resolve, 1000));

      console.log(`Processing: ${article.title}`);

      // Hämta detaljerat innehåll
      const { content, publishedAt } = await scrapeDiArticleContent(
        article.url
      );

      const completeArticle = {
        ...article,
        content,
        publishedAt: publishedAt || article.publishedAt,
      };

      completeArticles.push(completeArticle);

      // Lägg till i vår lista över processade URL:er
      processedUrls.add(article.url);
    }

    console.log(
      `Scraping slutförd. Processade ${completeArticles.length} nya artiklar`
    );

    // Uppdatera globala arrayen genom att lägga till de nya artiklarna i början
    scrapedArticles = [...completeArticles, ...scrapedArticles];

    // Spara till fil
    saveArticlesToFile();

    return {
      newArticles: completeArticles.length,
      totalStored: scrapedArticles.length,
    };
  } catch (error) {
    console.error("Fel vid scraping:", error);
    return { error: error.message };
  }
}

// API-endpoints
app.get("/api/scrape", async (req, res) => {
  try {
    const limit = parseInt(req.query.limit || "15", 10);
    const result = await scrapeAll(limit);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Hämta senaste artiklar med paginering
app.get("/api/articles", (req, res) => {
  try {
    const { limit = 20, offset = 0 } = req.query;
    const limitNum = parseInt(limit, 10);
    const offsetNum = parseInt(offset, 10);

    const paginatedArticles = scrapedArticles.slice(
      offsetNum,
      offsetNum + limitNum
    );

    res.json(paginatedArticles);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Hämta en specifik artikel med ID eller URL
app.get("/api/articles/:identifier", (req, res) => {
  try {
    const { identifier } = req.params;
    let article;

    // Kontrollera om identifier är ett index eller en URL
    if (!isNaN(identifier)) {
      // Om det är ett index/id
      const index = parseInt(identifier, 10);
      article = scrapedArticles[index];
    } else {
      // Om det är en URL (eller del av URL)
      article = scrapedArticles.find((a) => a.url.includes(identifier));
    }

    if (!article) {
      return res.status(404).json({ error: "Artikel hittades inte" });
    }

    res.json(article);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Hälsokontroll för att verifiera att servern körs
app.get("/health", (req, res) => {
  res.status(200).json({
    status: "UP",
    timestamp: new Date(),
    articleCount: scrapedArticles.length,
    message: "Di-scraper körs",
  });
});

// Schemalägg scraping att köra var 15:e minut
// Format: '*/15 * * * *' = Kör var 15:e minut
cron.schedule("*/15 * * * *", async () => {
  try {
    await scrapeAll();
  } catch (error) {
    console.error("Fel vid schemalagd scraping:", error);
  }
});

// Starta servern
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Server körs på port ${PORT}`);
  console.log(
    "Besök http://51.20.22.69:3000/api/scrape för att starta manuell scraping"
  );
  console.log(
    "Besök http://51.20.22.69:3000/api/articles för att se scrapade artiklar"
  );
  console.log("Schemalagd scraping kommer att köras var 15:e minut");

  // Kör en initial scraping när servern startas
  scrapeAll().catch((error) => {
    console.error("Fel vid initial scraping:", error);
  });
});

// Hantera oväntade fel för att förhindra att servern kraschar
process.on("uncaughtException", (error) => {
  console.error("Oväntat fel:", error);
  // Fortsätt köra servern trots felet
});

process.on("unhandledRejection", (reason, promise) => {
  console.error("Ohanterad Promise-rejection:", reason);
  // Fortsätt köra servern trots felet
});
