# Smart Shop MVP (FastAPI + Streamlit + PostgreSQL)

AI-powered e-commerce assistant with recommendations, price comparisons, review summarization, and store policy automation. The backend uses FastAPI + Pydantic, the UI is Streamlit, and data is stored in PostgreSQL. OpenAI powers the conversational layer.

## Features
- AI-driven recommendations
- Sentiment-based review summaries
- Real-time price comparison by category
- Store policy automation
- Conversational AI interface

## Prerequisites
- Docker Desktop
- OpenAI API key

## Run (Docker)
```bash
cd smart-shop-mvp
docker compose up --build
```

The app will be available at:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8501`

## Environment variables
- `OPENAI_API_KEY` (required for AI responses)
- `OPENAI_MODEL` (optional, default `gpt-4o-mini`)
- `SMART_SHOP_DATA_DIR` (path to the CSV folder)

Example:
```bash
set OPENAI_API_KEY=your_key
set SMART_SHOP_DATA_DIR=C:\Users\ashad\Downloads\Smart Shop
```

## Local (non-Docker) dev
Backend:
```bash
cd smart-shop-mvp\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg://smartshop:smartshop@localhost:5432/smartshop
set SMART_SHOP_DATA_DIR=C:\Users\ashad\Downloads\Smart Shop
set OPENAI_API_KEY=your_key
uvicorn app.main:app --reload
```

Frontend:
```bash
cd smart-shop-mvp\frontend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set API_BASE_URL=http://localhost:8000
streamlit run app.py
```

## Notes
- The API auto-seeds PostgreSQL on startup if tables are empty.
- CSVs must exist in `SMART_SHOP_DATA_DIR`:
  - `products.csv`
  - `reviews.csv`
  - `store_policies.csv`
- If `SMART_SHOP_DATA_DIR` is not set, the backend uses bundled CSVs in `smart-shop-mvp/backend/data`.
- Optional personalization CSVs:
  - `users.csv` (id,name,preferred_categories,budget_min,budget_max)
  - `user_events.csv` (user_id,product_id,event_type,date)
- If optional CSVs are missing, the API seeds sample user profiles.
- Legacy Node MVP files (`server.js`, `dataStore.js`, `public/`) are unused after the migration.

## Personalization
- Streamlit includes user creation and profile editing.
- Event tracking: `view`, `wishlist`, `purchase` improve personalized rankings.

## Policies
- `/policy` now supports `policy_type` (e.g., `returns`, `warranty`).
- Example: `/policy?category=laptop&policy_type=warranty`

## Product Order
- The products list follows the CSV order using a `row_index` column.
- If you already have an existing Postgres volume, recreate it to re-seed order:
  - `docker compose down -v`
  - `docker compose up --build`
