-- BörsRadar databas-schema
-- Kör detta skript för att skapa den initiala databasstrukturen

-- Skapa tabell för nyhetsartiklar
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    url VARCHAR(512) NOT NULL UNIQUE,
    image_url VARCHAR(512),
    source VARCHAR(100) NOT NULL DEFAULT 'DI',
    published_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Skapa index för snabb sökning
CREATE INDEX IF NOT EXISTS idx_news_published_date ON news_articles(published_date);
CREATE INDEX IF NOT EXISTS idx_news_source ON news_articles(source);

-- Skapa tabell för podcasts
CREATE TABLE IF NOT EXISTS podcasts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    last_analyzed TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(name)
);

-- Skapa tabell för podcastavsnitt
CREATE TABLE IF NOT EXISTS podcast_episodes (
    id SERIAL PRIMARY KEY,
    podcast_id INTEGER REFERENCES podcasts(id),
    title VARCHAR(255) NOT NULL,
    date VARCHAR(100),
    link VARCHAR(512) NOT NULL,
    description TEXT,
    has_transcript BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(podcast_id, link)
);

-- Skapa index för snabb sökning
CREATE INDEX IF NOT EXISTS idx_episodes_podcast_id ON podcast_episodes(podcast_id);
CREATE INDEX IF NOT EXISTS idx_episodes_date ON podcast_episodes(date);

-- Skapa tabell för aktieomtal
CREATE TABLE IF NOT EXISTS stock_mentions (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER REFERENCES podcast_episodes(id),
    stock_name VARCHAR(255) NOT NULL,
    context TEXT,
    sentiment VARCHAR(50),
    price_info TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Skapa index för snabb sökning av aktieomtal
CREATE INDEX IF NOT EXISTS idx_mentions_episode_id ON stock_mentions(episode_id);
CREATE INDEX IF NOT EXISTS idx_mentions_stock_name ON stock_mentions(stock_name);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON stock_mentions(sentiment);

-- Skapa tabell för aktier/bolag
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20),
    market VARCHAR(50),
    sector VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(name)
);

-- Skapa tabell för användarfavoriter (om du planerar att ha användarfunktionalitet)
CREATE TABLE IF NOT EXISTS user_favorites (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    stock_id INTEGER REFERENCES stocks(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, stock_id)
);

-- Skapa vy för att enkelt hämta alla aktieomtal med relaterad information
CREATE OR REPLACE VIEW stock_mentions_view AS
SELECT 
    sm.id,
    p.name AS podcast_name,
    pe.title AS episode_title,
    pe.date AS episode_date,
    pe.link AS episode_link,
    sm.stock_name,
    sm.context,
    sm.sentiment,
    sm.price_info,
    pe.has_transcript,
    sm.created_at
FROM stock_mentions sm
JOIN podcast_episodes pe ON sm.episode_id = pe.id
JOIN podcasts p ON pe.podcast_id = p.id
ORDER BY pe.date DESC, p.name ASC;

-- Funktion för att uppdatera timestamp när rader ändras
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers för att automatiskt uppdatera updated_at
CREATE TRIGGER update_news_articles_modtime
BEFORE UPDATE ON news_articles
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_stocks_modtime
BEFORE UPDATE ON stocks
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();