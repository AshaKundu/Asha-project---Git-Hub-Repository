import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { createDataStore } from "./dataStore.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json());

const dataStore = createDataStore({
  dataDir: process.env.SMART_SHOP_DATA_DIR
});

app.use(express.static(path.join(__dirname, "public")));

function asNumber(value) {
  if (value == null || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

app.get("/api/products", (req, res) => {
  const { query, category, minPrice, maxPrice, inStockOnly } = req.query;
  const results = dataStore.getProducts({
    query,
    category,
    minPrice: asNumber(minPrice),
    maxPrice: asNumber(maxPrice),
    inStockOnly: inStockOnly === "true"
  });
  res.json(results.slice(0, 50));
});

app.get("/api/recommendations", (req, res) => {
  const { productId, query } = req.query;
  res.json(dataStore.getRecommendations({ productId, query }));
});

app.get("/api/reviews/summary", (req, res) => {
  const { productId } = req.query;
  if (!productId) {
    res.status(400).json({ error: "productId required" });
    return;
  }
  res.json(dataStore.getReviewSummary(productId));
});

app.get("/api/price-compare", (req, res) => {
  const { productId } = req.query;
  if (!productId) {
    res.status(400).json({ error: "productId required" });
    return;
  }
  const comparison = dataStore.getPriceComparison(productId);
  if (!comparison) {
    res.status(404).json({ error: "product not found" });
    return;
  }
  res.json(comparison);
});

app.get("/api/policy", (req, res) => {
  const { productId, category } = req.query;
  if (productId) {
    const policy = dataStore.getPolicyForProduct(productId);
    if (!policy) {
      res.status(404).json({ error: "policy not found" });
      return;
    }
    res.json(policy);
    return;
  }

  if (category) {
    const policy = dataStore.getPolicyByCategory(category);
    if (!policy) {
      res.status(404).json({ error: "policy not found" });
      return;
    }
    res.json(policy);
    return;
  }

  res.status(400).json({ error: "productId or category required" });
});

function detectIntent(message) {
  const text = message.toLowerCase();
  if (text.includes("policy") || text.includes("return") || text.includes("warranty")) {
    return "policy";
  }
  if (text.includes("review") || text.includes("summary") || text.includes("sentiment")) {
    return "review";
  }
  if (text.includes("compare") || text.includes("price") || text.includes("cheaper")) {
    return "price";
  }
  if (text.includes("recommend") || text.includes("suggest") || text.includes("similar")) {
    return "recommend";
  }
  return "search";
}

app.post("/api/chat", (req, res) => {
  const { message, productId } = req.body || {};
  if (!message) {
    res.status(400).json({ error: "message required" });
    return;
  }

  const intent = detectIntent(message);
  let reply = "";
  let payload = {};

  if (intent === "policy") {
    let policy = null;
    if (productId) {
      policy = dataStore.getPolicyForProduct(productId);
    } else {
      const match = message.match(/(laptop|smartphone|speaker|tv|smart tv|smart_tv)/i);
      const category = match ? match[0].replace(" ", "_") : null;
      if (category) {
        policy = dataStore.getPolicyByCategory(category);
      }
    }

    if (policy) {
      reply = `Return policy: ${policy.description}. Timeframe: ${policy.timeframe} days.`;
      payload.policy = policy;
    } else {
      reply = "I couldn't find a matching policy. Tell me the product or category.";
    }
  } else if (intent === "review") {
    if (!productId) {
      reply = "Tell me the product ID for review summary.";
    } else {
      const summary = dataStore.getReviewSummary(productId);
      reply = `Review summary: ${summary.average_rating} avg rating from ${summary.total_reviews} reviews.`;
      payload.summary = summary;
    }
  } else if (intent === "price") {
    if (!productId) {
      reply = "Tell me the product ID to compare prices.";
    } else {
      const comparison = dataStore.getPriceComparison(productId);
      if (!comparison) {
        reply = "I couldn't find that product.";
      } else {
        reply = `Price range for ${comparison.base.category}: $${comparison.min} - $${comparison.max} (avg $${comparison.avg}).`;
        payload.comparison = comparison;
      }
    }
  } else if (intent === "recommend") {
    const recommendations = dataStore.getRecommendations({ productId, query: message });
    reply = "Here are some recommendations based on your request.";
    payload.recommendations = recommendations;
  } else {
    const results = dataStore.getProducts({ query: message, inStockOnly: true });
    reply = results.length ? "Here are matching products." : "I couldn't find a match. Try another query.";
    payload.results = results.slice(0, 8);
  }

  res.json({ reply, intent, payload });
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Smart Shop MVP running on http://localhost:${port}`);
});
