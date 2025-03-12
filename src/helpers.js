// Simulera en väntetid, användbar för testning av laddningstillstånd
export const waait = (ms = 1000) => new Promise((res) => setTimeout(res, ms));

// colors
const generateRandomColor = () => {
  const existingBudgetLength = fetchData("budgets")?.length ?? 0;
  return `${existingBudgetLength * 34} 65% 50%`;
};

// Local storage
export const fetchData = (key) => {
  return JSON.parse(localStorage.getItem(key));
};

// Get all items from local storage
export const getAllMatchingItems = ({ category, key, value }) => {
  const data = fetchData(category) ?? [];
  return data.filter((item) => item[key] === value);
};

// delete item from local storage
export const deleteItem = ({ key, id }) => {
  const existingData = fetchData(key);
  if (id) {
    const newData = existingData.filter((item) => item.id !== id);
    return localStorage.setItem(key, JSON.stringify(newData));
  }
  return localStorage.removeItem(key);
};

// FORMATTING
export const formatDateToLocaleString = (epoch) =>
  new Date(epoch).toLocaleDateString();

// Formating percentages
export const formatPercentage = (amt) => {
  return amt.toLocaleString(undefined, {
    style: "percent",
    minimumFractionDigits: 0,
  });
};

// Format currency
export const formatCurrency = (amt) => {
  return amt.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
};

// Funktion för att formatera datum
export const formatDate = (dateString) => {
  if (!dateString) return "Nyligen publicerad";

  // Om det är "I dag", returnera det
  if (dateString === "I dag") return dateString;

  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat("sv-SE", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date);
  } catch (e) {
    return dateString;
  }
};

// Funktion för att förkorta text om den är för lång
export const truncateText = (text, maxLength = 100) => {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
};

// Funktion för att cachelagra nyheter lokalt
export const cacheNewsData = (newsData) => {
  localStorage.setItem(
    "cachedNews",
    JSON.stringify({
      data: newsData,
      timestamp: Date.now(),
    })
  );
};

// Funktion för att hämta cacheade nyheter
export const getCachedNews = () => {
  const cachedData = localStorage.getItem("cachedNews");
  if (!cachedData) return null;

  try {
    const parsed = JSON.parse(cachedData);
    const cacheAge = Date.now() - parsed.timestamp;

    // Returnera cache om den är yngre än 10 minuter (600000 ms)
    if (cacheAge < 600000) {
      return parsed.data;
    }

    return null;
  } catch (e) {
    return null;
  }
};
