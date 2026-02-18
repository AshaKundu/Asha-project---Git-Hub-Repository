const state = {
  products: [],
  activeProduct: null
};

const productList = document.getElementById("productList");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const activeProduct = document.getElementById("activeProduct");
const insights = document.getElementById("insights");
const policy = document.getElementById("policy");
const chatLog = document.getElementById("chatLog");
const chatForm = document.getElementById("chatForm");
const chatMessage = document.getElementById("chatMessage");

function formatCurrency(value) {
  return `$${value.toFixed(2)}`;
}

function renderProducts(products) {
  productList.innerHTML = "";
  products.forEach((product) => {
    const card = document.createElement("div");
    card.className = "product";
    card.innerHTML = `
      <strong>${product.name}</strong>
      <span class="meta">${product.brand} · ${product.category}</span>
      <span class="price">${formatCurrency(product.price)} · Rating ${product.rating}</span>
      <span class="meta">Stock ${product.stock}</span>
    `;
    card.addEventListener("click", () => selectProduct(product));
    productList.appendChild(card);
  });
}

function renderInsights(summary, comparison) {
  const lines = [];
  if (summary) {
    lines.push(`Average rating ${summary.average_rating} from ${summary.total_reviews} reviews.`);
    lines.push(`Sentiment: ${summary.sentiment.positive} positive · ${summary.sentiment.neutral} neutral · ${summary.sentiment.negative} negative.`);
    if (summary.themes.length) {
      lines.push(`Themes: ${summary.themes.map((item) => item.word).join(", ")}.`);
    }
  }
  if (comparison) {
    lines.push(`Price range: ${formatCurrency(comparison.min)} to ${formatCurrency(comparison.max)} (avg ${formatCurrency(comparison.avg)}).`);
    if (comparison.cheaper.length) {
      lines.push(`Cheaper picks: ${comparison.cheaper.map((item) => item.name).slice(0, 3).join(", ")}.`);
    }
    lines.push(`Updated ${new Date(comparison.updated_at).toLocaleString()}.`);
  }
  insights.innerHTML = lines.map((line) => `<div>${line}</div>`).join("");
}

function renderPolicy(policyData) {
  if (!policyData) {
    policy.innerHTML = "No policy found.";
    return;
  }
  policy.innerHTML = `
    <div><strong>${policyData.description}</strong></div>
    <div>Timeframe: ${policyData.timeframe} days</div>
    <div>${policyData.conditions.join(" · ")}</div>
  `;
}

async function selectProduct(product) {
  state.activeProduct = product;
  activeProduct.textContent = `${product.name} · ${product.id}`;

  const [summary, comparison, policyData] = await Promise.all([
    fetch(`/api/reviews/summary?productId=${product.id}`).then((res) => res.json()),
    fetch(`/api/price-compare?productId=${product.id}`).then((res) => res.json()),
    fetch(`/api/policy?productId=${product.id}`).then((res) => res.json())
  ]);

  renderInsights(summary, comparison);
  renderPolicy(policyData);
}

function addMessage(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendMessage(message) {
  addMessage(message, "user");
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      productId: state.activeProduct ? state.activeProduct.id : null
    })
  });
  const data = await response.json();
  addMessage(data.reply, "assistant");
}

async function searchProducts() {
  const query = searchInput.value.trim();
  const response = await fetch(`/api/products?query=${encodeURIComponent(query)}&inStockOnly=true`);
  const products = await response.json();
  state.products = products;
  renderProducts(products);
}

searchButton.addEventListener("click", searchProducts);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    searchProducts();
  }
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = chatMessage.value.trim();
  if (!message) return;
  chatMessage.value = "";
  sendMessage(message);
});

async function init() {
  const response = await fetch("/api/recommendations");
  const products = await response.json();
  state.products = products;
  renderProducts(products);
  addMessage("Hi, I can compare prices, summarize reviews, or recommend products.", "assistant");
}

init();
