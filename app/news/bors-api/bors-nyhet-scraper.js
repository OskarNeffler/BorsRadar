// bors-nyhet-scraper.js - Scraper för börsnyheter (ingen inloggning krävs)
// Detta script körs via crontab och uppdaterar börsnyheterna regelbundet

// Ladda konfiguration från .env
require("dotenv").config({ path: "../.env" });

const axios = require("axios");
const cheerio = require("cheerio");
const fs = require("fs");
const path = require("path");
const { logger } = require("../delade/logger");

// <-- Viktigt: Importera din DB-funktion
const { saveStockNews } = require("../artikel-db/db-connector");

// Skapa mapp för sparad data om den inte finns
const DATA_DIR = path.join(__dirname, "data");
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Filsökväg för att spara börsnyheter i fil (frivilligt)
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

// Skapa en uppslagstabell för URL:er som vi redan har skrapat (för fil-lagring)
const processedUrls = new Set(stockNewsArticles.map((article) => article.url));

// Spara börsnyheter till fil (frivilligt)
function saveArticlesToFile() {
  try {
    fs.writeFileSync(
      STOCK_NEWS_FILE,
      JSON.stringify(stockNewsArticles, null, 2),
      "utf8"
    );
    logger.info(`Sparade ${stockNewsArticles.length} börsnyheter till fil`);
  } catch (error) {
    logger.error("Fel vid sparande av börsnyheter till fil:", error);
  }
}

// URLs för scraping
const DI_BASE_URL = "https://www.di.se";
const DI_STOCK_NEWS_URL = "https://www.di.se/bors/nyheter/";

// Funktion för att scrapa börsnyheter från DI
async function scrapeStockNewsList() {
  try {
    logger.info(`Hämtar börsnyheter från ${DI_STOCK_NEWS_URL}`);

    const response = await axios.get(DI_STOCK_NEWS_URL);
    const $ = cheerio.load(response.data);
    const articles = [];

    $(".news-item__content-wrapper").each((index, element) => {
      try {
        // Hämta länk till artikeln
        const linkElement = $(element).find("a").first();
        const relativeUrl = linkElement.attr("href");
        if (!relativeUrl) {
          logger.debug("Hoppar över artikel utan URL");
          return;
        }

        const url = relativeUrl.startsWith("/")
          ? `${DI_BASE_URL}${relativeUrl}`
          : relativeUrl;

        // Kontrollera om vi redan har denna URL i fil-lagringen
        if (processedUrls.has(url)) {
          logger.debug(`Hoppar över redan processad börsnyhet: ${url}`);
          return;
        }

        // Hämta titel
        const title = $(element).find(".news-item__heading").text().trim();
        // Hämta sammanfattning
        const summary = $(element).find(".news-item__text").text().trim();

        // Hämta bild-URL
        let imageUrl = null;
        const parentDiv = $(element).closest(".news-item__content");
        const imgElement = parentDiv.find(".image__el");
        if (imgElement.length > 0) {
          if (imgElement.attr("srcset")) {
            const srcsetUrls = imgElement.attr("srcset").split(",");
            const largestImage = srcsetUrls[srcsetUrls.length - 1]
              .trim()
              .split(" ")[0];
            imageUrl = largestImage;
          } else {
            imageUrl = imgElement.attr("src");
          }
        }

        // Hämta tidsstämpel
        let publishDate = null;
        const timeElement = parentDiv.find("time");
        if (timeElement.length > 0) {
          const dateTimeStr = timeElement.attr("datetime");
          if (dateTimeStr) {
            publishDate = new Date(dateTimeStr);
          }
        }

        if (title && url) {
          articles.push({
            title,
            url,
            summary,
            imageUrl,
            source: "di",
            type: "stock_news",
            publishedAt: publishDate || new Date(),
            scrapedAt: new Date(),
          });
        }
      } catch (itemError) {
        logger.error(
          `Fel vid bearbetning av artikel ${index}:`,
          itemError.message
        );
      }
    });

    logger.info(`Hittade ${articles.length} nya börsnyheter`);
    return articles;
  } catch (error) {
    logger.error(`Fel vid scraping av börsnyheter:`, error.message);
    return [];
  }
}

// Huvudfunktion för att scrapa börsnyheter
async function scrapeStockNews(limit = 15) {
  try {
    logger.info(
      `[${new Date().toLocaleString()}] Startar scraping av börsnyheter...`
    );

    // 1. Hämta alla börsnyheter
    const newStockNews = await scrapeStockNewsList();

    // 2. Om inga nya börsnyheter hittades, avsluta
    if (newStockNews.length === 0) {
      logger.info("Inga nya börsnyheter hittades.");
      return {
        newArticles: 0,
        totalStored: stockNewsArticles.length,
      };
    }

    // 3. Begränsa antalet artiklar att processa i denna körning
    const newsToProcess = newStockNews.slice(0, limit);

    // 4. **Spara i databasen** (viktigt!)
    //    Detta gör att artiklarna lagras utan dubbletter pga. ON CONFLICT
    await saveStockNews(newsToProcess);

    // 5. Lägg till varje URL i "processedUrls" (för fil-lagringens skull)
    newsToProcess.forEach((news) => {
      processedUrls.add(news.url);
    });

    // 6. Uppdatera den globala arrayen med nya nyheter först
    stockNewsArticles = [...newsToProcess, ...stockNewsArticles];

    // 7. Begränsa storleken på fil-lagringen
    const maxArticles = parseInt(process.env.BORS_MAX_ARTICLES || 500, 10);
    if (stockNewsArticles.length > maxArticles) {
      stockNewsArticles = stockNewsArticles.slice(0, maxArticles);
    }

    // 8. Spara även i fil (om du vill fortsätta ha en lokal JSON-kopia)
    saveArticlesToFile();

    return {
      newArticles: newsToProcess.length,
      totalStored: stockNewsArticles.length,
    };
  } catch (error) {
    logger.error("Fel vid scraping av börsnyheter:", error);
    return { error: error.message };
  }
}

// Kör när scriptet anropas direkt (t.ex. via "node bors-nyhet-scraper.js")
if (require.main === module) {
  scrapeStockNews()
    .then((result) => {
      logger.info(`Scraping slutförd: ${JSON.stringify(result)}`);
      process.exit(0);
    })
    .catch((error) => {
      logger.error("Fel vid körning av scraper:", error);
      process.exit(1);
    });
}

// Exportera för användning i andra filer
module.exports = {
  scrapeStockNews,
};
