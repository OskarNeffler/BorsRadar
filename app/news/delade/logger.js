// logger.js - Gemensam loggningsfunktionalitet för hela applikationen

// Ladda konfiguration från .env
require("dotenv").config({ path: "../.env" });
const fs = require("fs");
const path = require("path");
const util = require("util");

// Globala konfigurationer
const LOG_LEVEL = process.env.LOG_LEVEL || "info";
const LOG_LEVELS = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

// Skapa en timestamp med ISO-format
function getTimestamp() {
  return new Date().toISOString();
}

// Formatera loggmeddelande
function formatLogMessage(level, message, ...args) {
  let formattedMessage = `[${getTimestamp()}] [${level.toUpperCase()}] ${message}`;

  // Hantera ytterligare argument
  if (args.length > 0) {
    formattedMessage +=
      " " +
      args
        .map((arg) => {
          if (typeof arg === "object") {
            return util.inspect(arg, { depth: null, colors: false });
          }
          return arg;
        })
        .join(" ");
  }

  return formattedMessage;
}

// Skapa logger-objekt
const logger = {
  error: function (message, ...args) {
    if (LOG_LEVELS[LOG_LEVEL] >= LOG_LEVELS.error) {
      const logMessage = formatLogMessage("ERROR", message, ...args);
      console.error(logMessage);
      this.writeToLogFile(logMessage);
    }
  },

  warn: function (message, ...args) {
    if (LOG_LEVELS[LOG_LEVEL] >= LOG_LEVELS.warn) {
      const logMessage = formatLogMessage("WARN", message, ...args);
      console.warn(logMessage);
      this.writeToLogFile(logMessage);
    }
  },

  info: function (message, ...args) {
    if (LOG_LEVELS[LOG_LEVEL] >= LOG_LEVELS.info) {
      const logMessage = formatLogMessage("INFO", message, ...args);
      console.info(logMessage);
      this.writeToLogFile(logMessage);
    }
  },

  debug: function (message, ...args) {
    if (LOG_LEVELS[LOG_LEVEL] >= LOG_LEVELS.debug) {
      const logMessage = formatLogMessage("DEBUG", message, ...args);
      console.debug(logMessage);
      this.writeToLogFile(logMessage);
    }
  },

  // Skriv loggar till fil
  writeToLogFile: function (message) {
    try {
      // Identifiera vilken del av applikationen som anropar loggern
      const callerPath = getCallerPath();
      const logDir = path.join(path.dirname(callerPath), "logs");

      // Skapa logs-mappen om den inte finns
      if (!fs.existsSync(logDir)) {
        fs.mkdirSync(logDir, { recursive: true });
      }

      // Skapa en loggfil baserat på dagens datum
      const today = new Date().toISOString().split("T")[0];
      const logFile = path.join(logDir, `${today}.log`);

      // Lägg till i loggfilen
      fs.appendFileSync(logFile, message + "\n");
    } catch (error) {
      console.error(`Kunde inte skriva till loggfil: ${error.message}`);
    }
  },
};

// Hjälpfunktion för att identifiera vilken del av applikationen som anropar loggern
function getCallerPath() {
  const stack = new Error().stack;
  const callerLine = stack.split("\n")[3]; // 0 är Error, 1 är getCurrentFilePath, 2 är logger-metod, 3 är caller

  // Extrahera sökvägen från stackspåret (detta kan behöva anpassas beroende på miljö)
  const match = callerLine.match(/at\s+(?:\w+\s+\()?([^:]+):/);

  if (match && match[1]) {
    return match[1];
  }

  // Fallback: använd aktuell katalog
  return process.cwd();
}

module.exports = {
  logger,
};
