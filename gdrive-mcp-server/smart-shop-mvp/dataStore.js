import fs from "fs";
import path from "path";
import { parse } from "csv-parse/sync";

const DEFAULT_DATA_DIR = "C:/Users/ashad/Downloads/Smart Shop";

const CATEGORY_POLICY_MAP = {
  laptop: "Laptop Return Policy",
  smartphone: "Smartphone Return Policy",
  smart_tv: "Smart TV Return Policy",
  speaker: "Speaker Return Policy"
};

const STOPWORDS = new Set([
  "the", "and", "a", "an", "is", "it", "this", "that", "to", "of", "for", "in", "on", "with",
  "very", "really", "my", "our", "your", "all", "at", "as", "was", "were", "be", "are", "but",
  "so", "if", "by", "from", "has", "have", "had", "its", "i", "me", "we", "you", "they"
]);

const SENTIMENT_LEXICON = {
  positive: ["great", "excellent", "amazing", "love", "fast", "snappy", "beautiful", "clear", "crystal", "smooth", "awesome", "perfect", "good", "durable", "battery", "bright"],
  negative: ["bad", "poor", "slow", "broken", "cracked", "damage", "overheats", "lag", "laggy", "heavy", "dim", "terrible", "awful", "disappoint", "noisy"]
};

function loadCsv(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  return parse(text, { columns: true, skip_empty_lines: true, trim: true });
}

function parsePolicies(rows) {
  return rows.map((row) => ({
    policy_type: row.policy_type,
    description: row.description,
    conditions: row.conditions ? row.conditions.split("|") : [],
    timeframe: Number(row.timeframe)
  }));
}

function normalizeText(text) {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, " ");
}

function tokenize(text) {
  return normalizeText(text)
    .split(/\s+/)
    .filter((token) => token && !STOPWORDS.has(token));
}

function scoreSentiment(text) {
  const tokens = tokenize(text);
  let score = 0;
  for (const token of tokens) {
    if (SENTIMENT_LEXICON.positive.includes(token)) score += 1;
    if (SENTIMENT_LEXICON.negative.includes(token)) score -= 1;
  }
  return score;
}

function summarizeReviews(reviews) {
  if (reviews.length === 0) {
    return {
      average_rating: 0,
      total_reviews: 0,
      sentiment: { positive: 0, neutral: 0, negative: 0 },
      themes: []
    };
  }

  let total = 0;
  let positive = 0;
  let negative = 0;
  let neutral = 0;
  const wordCounts = new Map();

  for (const review of reviews) {
    total += Number(review.rating) || 0;
    const sentimentScore = scoreSentiment(review.text || "");
    if (review.rating >= 4 || sentimentScore > 0) positive += 1;
    else if (review.rating <= 2 || sentimentScore < 0) negative += 1;
    else neutral += 1;

    for (const token of tokenize(review.text || "")) {
      wordCounts.set(token, (wordCounts.get(token) || 0) + 1);
    }
  }

  const themes = [...wordCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([word, count]) => ({ word, count }));

  return {
    average_rating: Number((total / reviews.length).toFixed(2)),
    total_reviews: reviews.length,
    sentiment: { positive, neutral, negative },
    themes
  };
}

function getTextScore(product, queryTokens) {
  const haystack = `${product.name} ${product.brand} ${product.category} ${product.description}`.toLowerCase();
  let score = 0;
  for (const token of queryTokens) {
    if (haystack.includes(token)) score += 2;
  }
  return score;
}

function scoreRecommendation(baseProduct, candidate) {
  const priceDiff = Math.abs(candidate.price - baseProduct.price);
  const priceScore = 1 - Math.min(priceDiff / Math.max(baseProduct.price, 1), 1);
  const stockScore = candidate.stock > 0 ? 1 : 0;
  return (candidate.rating || 0) * 2 + priceScore + stockScore;
}

export function createDataStore({ dataDir = DEFAULT_DATA_DIR } = {}) {
  const productsPath = path.join(dataDir, "products.csv");
  const reviewsPath = path.join(dataDir, "reviews.csv");
  const policiesPath = path.join(dataDir, "store_policies.csv");

  let cache = null;
  let lastLoaded = 0;
  let lastModified = 0;

  function getLastModified(paths) {
    return Math.max(
      ...paths.map((p) => (fs.existsSync(p) ? fs.statSync(p).mtimeMs : 0))
    );
  }

  function load() {
    const products = loadCsv(productsPath).map((row) => ({
      id: row.id,
      name: row.name,
      brand: row.brand,
      category: row.category,
      price: Number(row.price),
      description: row.description,
      stock: Number(row.stock),
      rating: Number(row.rating)
    }));

    const reviews = loadCsv(reviewsPath).map((row) => ({
      product_id: row.product_id,
      rating: Number(row.rating),
      text: row.text,
      date: row.date
    }));

    const policies = parsePolicies(loadCsv(policiesPath));

    const productById = new Map(products.map((product) => [product.id, product]));
    const reviewsByProduct = new Map();
    for (const review of reviews) {
      if (!reviewsByProduct.has(review.product_id)) {
        reviewsByProduct.set(review.product_id, []);
      }
      reviewsByProduct.get(review.product_id).push(review);
    }

    cache = {
      products,
      productById,
      reviews,
      reviewsByProduct,
      policies
    };

    lastLoaded = Date.now();
    lastModified = getLastModified([productsPath, reviewsPath, policiesPath]);
  }

  function ensureFresh() {
    const now = Date.now();
    if (!cache || now - lastLoaded > 30000) {
      const currentModified = getLastModified([productsPath, reviewsPath, policiesPath]);
      if (!cache || currentModified > lastModified) {
        load();
      }
    }
  }

  function getProducts(filters = {}) {
    ensureFresh();
    let results = cache.products;

    if (filters.category) {
      results = results.filter((product) => product.category === filters.category);
    }

    if (filters.query) {
      const tokens = tokenize(filters.query);
      results = results
        .map((product) => ({
          product,
          score: getTextScore(product, tokens)
        }))
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score)
        .map((item) => item.product);
    }

    if (filters.minPrice != null) {
      results = results.filter((product) => product.price >= filters.minPrice);
    }

    if (filters.maxPrice != null) {
      results = results.filter((product) => product.price <= filters.maxPrice);
    }

    if (filters.inStockOnly) {
      results = results.filter((product) => product.stock > 0);
    }

    return results;
  }

  function getRecommendations({ productId, query }) {
    ensureFresh();
    if (productId && cache.productById.has(productId)) {
      const baseProduct = cache.productById.get(productId);
      return cache.products
        .filter((product) => product.category === baseProduct.category && product.id !== productId)
        .map((product) => ({ product, score: scoreRecommendation(baseProduct, product) }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 6)
        .map((item) => item.product);
    }

    if (query) {
      const tokens = tokenize(query);
      return cache.products
        .map((product) => ({ product, score: getTextScore(product, tokens) + product.rating }))
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 6)
        .map((item) => item.product);
    }

    return cache.products
      .slice()
      .sort((a, b) => b.rating - a.rating)
      .slice(0, 6);
  }

  function getReviewSummary(productId) {
    ensureFresh();
    const reviews = cache.reviewsByProduct.get(productId) || [];
    return summarizeReviews(reviews);
  }

  function getPriceComparison(productId) {
    ensureFresh();
    const product = cache.productById.get(productId);
    if (!product) return null;

    const categoryProducts = cache.products.filter((p) => p.category === product.category);
    const prices = categoryProducts.map((p) => p.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const avg = prices.reduce((sum, price) => sum + price, 0) / prices.length;

    const cheaper = categoryProducts
      .filter((p) => p.price < product.price)
      .sort((a, b) => a.price - b.price)
      .slice(0, 5);

    return {
      base: product,
      min: Number(min.toFixed(2)),
      max: Number(max.toFixed(2)),
      avg: Number(avg.toFixed(2)),
      cheaper,
      updated_at: new Date(lastModified).toISOString()
    };
  }

  function getPolicyForProduct(productId) {
    ensureFresh();
    const product = cache.productById.get(productId);
    if (!product) return null;

    const policyName = CATEGORY_POLICY_MAP[product.category];
    return cache.policies.find((policy) => policy.description === policyName) || null;
  }

  function getPolicyByCategory(category) {
    ensureFresh();
    const policyName = CATEGORY_POLICY_MAP[category];
    return cache.policies.find((policy) => policy.description === policyName) || null;
  }

  function getProductById(productId) {
    ensureFresh();
    return cache.productById.get(productId);
  }

  return {
    getProducts,
    getRecommendations,
    getReviewSummary,
    getPriceComparison,
    getPolicyForProduct,
    getPolicyByCategory,
    getProductById
  };
}
