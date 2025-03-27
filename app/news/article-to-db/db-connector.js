// db-connector.js
const { Pool } = require("pg");
const { logger } = require("../delade/logger");

// Skapa en pool med anslutningsinfo från .env
const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  ssl: {
    rejectUnauthorized: false, // Aktivera SSL men acceptera självsignerade certifikat
  },
});

/**
 * Sparar (eller uppdaterar) börsnyheter i tabellen news_articles.
 * Kräver en unik constraint på (url, published_at).
 */
async function saveStockNews(articles) {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");

    const query = `
      INSERT INTO news_articles 
        (title, url, summary, image_url, published_at, source) 
      VALUES ($1, $2, $3, $4, $5, $6)
      ON CONFLICT (url, published_at) DO UPDATE 
        SET summary = EXCLUDED.summary,
            image_url = EXCLUDED.image_url
    `;

    let savedCount = 0;
    for (const article of articles) {
      // Om publishedAt saknas, sätt default till nu
      const publishedAt = article.publishedAt || new Date();

      const result = await client.query(query, [
        article.title,
        article.url,
        article.summary || "",
        article.imageUrl || null,
        publishedAt,
        article.source || "di",
      ]);

      // rowCount > 0 innebär att en rad skapades eller uppdaterades
      if (result.rowCount > 0) {
        savedCount++;
      }
    }

    await client.query("COMMIT");
    logger.info(`Sparade ${savedCount} av ${articles.length} börsnyheter`);
    return savedCount;
  } catch (error) {
    await client.query("ROLLBACK");
    logger.error("Fel vid sparande av börsnyheter:", error);
    return 0;
  } finally {
    client.release();
  }
}

/**
 * Uppdaterar en artikel med fullständigt innehåll
 * (content, authors, tags) om den redan finns i tabellen.
 */
async function saveFullArticle(article) {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");

    const query = `
      UPDATE news_articles 
        SET content = $1,
            full_article_scraped = TRUE,
            authors = $2,
            tags = $3
      WHERE url = $4
      RETURNING id
    `;

    const result = await client.query(query, [
      article.content || "",
      article.authors ? JSON.stringify(article.authors) : null,
      article.tags ? JSON.stringify(article.tags) : null,
      article.url,
    ]);

    await client.query("COMMIT");

    if (result.rowCount > 0) {
      logger.info(`Uppdaterade fullständig artikel: ${article.title}`);
      return result.rows[0].id;
    }

    logger.warn(`Kunde inte uppdatera artikel med URL: ${article.url}`);
    return null;
  } catch (error) {
    await client.query("ROLLBACK");
    logger.error("Fel vid sparande av fullständig artikel:", error);
    return null;
  } finally {
    client.release();
  }
}

/**
 * Hämtar artiklar med paginering och valfritt filter
 * för att bara hämta artiklar med full_article_scraped = TRUE.
 */
async function getArticles(limit = 20, offset = 0, fullArticlesOnly = false) {
  const client = await pool.connect();

  try {
    const baseQuery = fullArticlesOnly
      ? "WHERE full_article_scraped = TRUE"
      : "";

    // Hämta totalt antal artiklar (för paginering)
    const countResult = await client.query(`
      SELECT COUNT(*) FROM news_articles ${baseQuery}
    `);
    const total = parseInt(countResult.rows[0].count);

    // Hämta själva artiklarna
    const result = await client.query(
      `
      SELECT * FROM news_articles 
      ${baseQuery}
      ORDER BY published_at DESC 
      LIMIT $1 OFFSET $2
    `,
      [limit, offset]
    );

    return {
      total,
      offset,
      limit,
      articles: result.rows,
    };
  } catch (error) {
    logger.error("Fel vid hämtning av artiklar:", error);
    return { total: 0, offset, limit, articles: [] };
  } finally {
    client.release();
  }
}

// Exportera funktionerna
module.exports = {
  saveStockNews,
  saveFullArticle,
  getArticles,
};
