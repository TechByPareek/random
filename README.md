# Wind Forecast Monitor

A web app that helps a UK energy buyer decide how much power to buy from the day-ahead market. It shows the latest wind forecast available at decision time and measures how accurate the forecasts were.

**Live app:** [https://random-six-sage.vercel.app](https://random-six-sage.vercel.app)

## What it does

1. Shows the latest wind forecast available at the decision moment (default 09:00 UTC on the day before delivery), with a typical error range.
2. Measures forecast accuracy against actual generation (MAE, RMSE, bias, P90/P99 error) in two modes: "Decision time" and "Hours ahead".
3. Shows how error changes with forecast horizon, with hour of day, and with the forecast wind level.

## Key findings (January 2026, decision-time mode)

- Typical miss (MAE): about 2,022 MW, which is about 17.9% of average wind output.
- Bias: forecasts were on average about 1,746 MW higher than the actual generation.
- 9 out of 10 hours were within about 4,154 MW of the forecast (P90 absolute error).
- The error is largest when the forecast is high. When the forecast was above 15 GW (298 of 744 hours) it was too high by about 2,683 MW on average. Below 9 GW the average error was small.
- A time-shift check between forecasts and actuals found no timing offset, so the bias does not appear to come from misaligned timestamps.
- The cause of the bias has not been established. Next step: test whether the same pattern appears in other months before relying on any correction.

## Scope and method

- Data: Elexon BMRS only. `FUELHH` (actual wind generation, fuel type WIND) and `WINDFOR` (wind forecasts with publish time).
- Scope: purchase decisions made 1-31 January 2026, for delivery on the next day (2 January - 1 February 2026). National wind only.
- Key rule: only forecasts published at or before the decision time are used. Later forecasts are never used.
- Assumption: decision time is 09:00 UTC on the day before delivery (changeable in the app).
- Forecasts are hourly, so 744 hours are compared.
- Error = forecast minus actual (positive = forecast too high).
- Limitations: one month of data; the "likely range" uses the whole month's P90 error; the cause of the observed bias has not been established.

## Files and directories

```
.
├── api/index.py              Vercel entry point (exposes the FastAPI app)
├── backend/
│   ├── app/main.py           FastAPI app: data loading, forecast selection, metrics, API endpoints
│   ├── data/                 Cached January 2026 data (actuals.csv, forecasts.csv)
│   ├── scripts/
│   │   ├── fetch_data.py     Downloads data from the Elexon API into backend/data
│   │   ├── check_data.py     Quick data sanity checks
│   │   └── check_alignment.py  Checks for time offsets between forecasts and actuals
│   ├── tests/test_logic.py   Unit tests for the forecast-selection rules and metrics
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── frontend/                 React (Vite) app with Recharts
│   ├── src/App.jsx           Main page
│   ├── src/App.css           Styles
│   ├── index.html            HTML entry point
│   ├── package.json          Frontend dependencies and scripts
│   ├── vite.config.js        Vite config (proxies /api to the backend in development)
│   ├── nginx.conf            Serves the build and proxies /api to the backend (Docker)
│   ├── Dockerfile
│   └── .dockerignore
├── docker-compose.yml        Runs frontend and backend together
├── requirements.txt          Python dependencies for the Vercel deployment
├── vercel.json               Vercel build and routing configuration
├── .gitignore
└── README.md
```

## How to start the application

### With Docker (recommended)

```bash
docker compose up --build
```

Then open http://localhost:3100

### Without Docker

Backend:

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Frontend (second terminal):

```bash
cd frontend
npm install
npm run dev
```

Open the address printed by Vite (usually http://localhost:5173).

### Refresh the data (optional)

```bash
python backend/scripts/fetch_data.py
```

### Run tests

```bash
pip install pytest
python -m pytest backend/tests -v
```

## AI tools used

I used Claude (Anthropic) to assist with planning, code, debugging and documentation. I reviewed, ran and tested the results myself.