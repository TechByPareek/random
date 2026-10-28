import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, ComposedChart, Area, ReferenceLine,
} from "recharts";
import "./App.css";

const fmt = (n) =>
  n == null || Number.isNaN(n) ? "–" : Math.round(n).toLocaleString();
const hh = (h) => String(h).padStart(2, "0");
const shortTime = (t) => (t ? t.slice(5, 16).replace("T", " ") : "");

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("Request failed: " + r.status);
  return r.json();
}

function Card({ label, value, unit = "MW", hint, warn }) {
  return (
    <div className={"card" + (warn ? " warn" : "")} title={hint}>
      <div className="card-label">{label}</div>
      <div className="card-value">
        {value}
        <span> {unit}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState("decision"); // "decision" | "horizon"
  const [horizon, setHorizon] = useState(24);
  const [decisionHour, setDecisionHour] = useState(9);
  const [start, setStart] = useState("2026-01-02");
  const [end, setEnd] = useState("2026-02-01");
  const [decisionDate, setDecisionDate] = useState("2026-01-14");

  const [headline, setHeadline] = useState({});
  const [series, setSeries] = useState({ points: [], metrics: {} });
  const [byHorizon, setByHorizon] = useState([]);
  const [byHour, setByHour] = useState([]);
  const [byLevel, setByLevel] = useState([]);
  const [decision, setDecision] = useState({ points: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // "At a glance" numbers: whole period, decision-time mode
  useEffect(() => {
    getJSON(`/api/series?mode=decision&decision_hour=${decisionHour}`)
      .then((d) => setHeadline(d.metrics || {}))
      .catch(() => setHeadline({}));
  }, [decisionHour]);

  // Accuracy section
  useEffect(() => {
    setLoading(true);
    setError("");
    const q = `mode=${mode}&horizon=${horizon}&decision_hour=${decisionHour}`;
    Promise.all([
      getJSON(
        `/api/series?start=${start}T00:00:00Z&end=${end}T23:30:00Z&${q}`
      ),
      getJSON(`/api/error-by-hour?${q}`),
      getJSON(`/api/bias-by-forecast-level?${q}`),
    ])
      .then(([s, h, l]) => {
        setSeries(s);
        setByHour(h);
        setByLevel(l);
      })
      .catch(() => setError("Could not load data. Is the backend running?"))
      .finally(() => setLoading(false));
  }, [mode, horizon, decisionHour, start, end]);

  // Error vs horizon (loaded once)
  useEffect(() => {
    getJSON("/api/metrics-by-horizon").then(setByHorizon).catch(() => {});
  }, []);

  // "What do I buy tomorrow" section
  useEffect(() => {
    getJSON(
      `/api/decision?decision_time=${decisionDate}T${hh(decisionHour)}:00:00Z`
    )
      .then(setDecision)
      .catch(() => setDecision({ points: [] }));
  }, [decisionDate, decisionHour]);

  const m = series.metrics || {};
  const biasPct = m.mean_actual ? (m.bias / m.mean_actual) * 100 : null;

  const decisionData = decision.points.map((p) => ({
    ...p,
    band: [p.low, p.high],
  }));
  const fvals = decision.points.map((p) => p.forecast);
  const dPeak = fvals.length ? Math.max(...fvals) : null;
  const dLow = fvals.length ? Math.min(...fvals) : null;
  const dAvg = fvals.length
    ? fvals.reduce((a, b) => a + b, 0) / fvals.length
    : null;

  const levelData = byLevel.map((l) => ({
    ...l,
    label: `${l.level} (${l.n}h)`,
  }));

  const hb = headline.bias;

  return (
    <div className="page">
      <header className="banner">
        <h1>Wind Forecast Monitor</h1>
        <p>
          UK national wind generation · Elexon FUELHH (actual) &amp; WINDFOR
          (forecast) · Day-ahead decisions made 1–31 January 2026 (delivery
          2 January – 1 February)
        </p>
      </header>

      {/* ---------- At a glance ---------- */}
      <section className="panel hero">
        <h2>January 2026 at a glance</h2>
        <div className="hero-grid">
          <div>
            <div className="hero-num">{fmt(headline.mae)} MW</div>
            <div className="hero-label">
              typical miss per hour (MAE), about{" "}
              {headline.nmae_pct ? headline.nmae_pct.toFixed(1) : "–"}% of
              average wind output
            </div>
          </div>
          <div>
            <div className="hero-num warn">
              {hb == null ? "–" : (hb >= 0 ? "+" : "−") + fmt(Math.abs(hb))} MW
            </div>
            <div className="hero-label">
              average bias: {hb != null && hb < 0 ? "forecasts ran lower" : "forecasts ran higher"} than
              the actual generation
            </div>
          </div>
          <div>
            <div className="hero-num">±{fmt(headline.p90_abs_error)} MW</div>
            <div className="hero-label">
              9 out of 10 hours were within this distance of the forecast
            </div>
          </div>
        </div>
        <p className="note">
          Based on the latest forecast available at {hh(decisionHour)}:00 UTC
          the day before delivery · {fmt(headline.n)} hours compared
        </p>
      </section>

      {/* ---------- Section 1 ---------- */}
      <section className="panel">
        <h2>1. How much wind can I expect tomorrow?</h2>
        <p className="sub">
          The latest forecast that was available at the moment you had to
          decide (default 09:00 UTC the day before), with a typical error
          range around it.
        </p>
        <div className="controls">
          <label>
            Decision day
            <input
              type="date"
              value={decisionDate}
              min="2026-01-01"
              max="2026-01-31"
              onChange={(e) => setDecisionDate(e.target.value)}
            />
          </label>
          <label>
            Decision time (UTC)
            <select
              value={decisionHour}
              onChange={(e) => setDecisionHour(+e.target.value)}
            >
              {[6, 7, 8, 9, 10, 11, 12].map((h) => (
                <option key={h} value={h}>
                  {hh(h)}:00
                </option>
              ))}
            </select>
          </label>
        </div>

        {decision.points.length === 0 ? (
          <p className="note">No forecast data for this decision day.</p>
        ) : (
          <>
            <div className="cards">
              <Card label="Delivery day" value={(decision.delivery_day || "").slice(0, 10)} unit="" />
              <Card label="Average forecast" value={fmt(dAvg)} />
              <Card label="Peak forecast" value={fmt(dPeak)} />
              <Card label="Lowest forecast" value={fmt(dLow)} />
              <Card
                label="Typical error (P90)"
                value={"±" + fmt(decision.p90_abs_error)}
                hint="In 9 of 10 hours, the forecast was this close or closer."
              />
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={decisionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="t" tickFormatter={(t) => t.slice(11, 16)} minTickGap={30} />
                <YAxis unit=" MW" width={90} tickFormatter={fmt} />
                <Tooltip
                  labelFormatter={shortTime}
                  formatter={(v) =>
                    Array.isArray(v)
                      ? fmt(v[0]) + " – " + fmt(v[1]) + " MW"
                      : fmt(v) + " MW"
                  }
                />
                <Legend />
                <Area dataKey="band" name="Likely range" fill="#bcd4f6" stroke="none" />
                <Line dataKey="forecast" name="Forecast" stroke="#1f5fbf" dot={false} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="note">
              The likely range uses the typical (P90) error measured over the
              whole of January, so treat it as a guide, not a guarantee.
            </p>
          </>
        )}
      </section>

      {/* ---------- Section 2 ---------- */}
      <section className="panel">
        <h2>2. How accurate are the forecasts?</h2>

        <details className="glossary">
          <summary>What do these numbers mean?</summary>
          <ul className="plain">
            <li><b>MAE</b>: the average size of the miss, ignoring whether it was too high or too low.</li>
            <li><b>RMSE</b>: like MAE, but big misses count more, so it shows how bad the worst misses are.</li>
            <li><b>Bias</b>: forecast minus actual, averaged. Above zero means forecasts were too high on average.</li>
            <li><b>P90 / P99 absolute error</b>: 90% (or 99%) of hours missed by no more than this amount.</li>
            <li><b>MAE / mean output</b>: the average miss as a share of the average wind generation.</li>
          </ul>
        </details>

        <div className="controls">
          <div className="tabs">
            <button
              className={mode === "decision" ? "active" : ""}
              onClick={() => setMode("decision")}
            >
              Decision time
            </button>
            <button
              className={mode === "horizon" ? "active" : ""}
              onClick={() => setMode("horizon")}
            >
              Hours ahead
            </button>
          </div>
          {mode === "horizon" && (
            <label>
              Forecast made at least <b>{horizon}h</b> ahead
              <input
                type="range"
                min="0"
                max="66"
                value={horizon}
                onChange={(e) => setHorizon(+e.target.value)}
              />
            </label>
          )}
          <label>
            From
            <input type="date" value={start} min="2026-01-02" max={end} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            To
            <input type="date" value={end} min={start} max="2026-02-01" onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        <p className="note">
          {mode === "decision"
            ? `Each hour uses the latest forecast published by ${hh(decisionHour)}:00 UTC the day before delivery.`
            : `Each hour uses the latest forecast published at least ${horizon} hours before delivery.`}{" "}
          Forecasts are hourly, so {fmt(m.n)} hours are compared.
        </p>

        <div className="cards">
          <Card label="MAE" value={fmt(m.mae)} hint="Mean absolute error: the average size of the miss" />
          <Card label="RMSE" value={fmt(m.rmse)} hint="Like MAE but big misses count more" />
          <Card label="Bias" value={fmt(m.bias)} warn hint="Forecast minus actual, averaged. Positive = forecasts too high" />
          <Card label="P90 abs error" value={fmt(m.p90_abs_error)} hint="9 in 10 hours are within this" />
          <Card label="P99 abs error" value={fmt(m.p99_abs_error)} hint="Near worst-case planning figure" />
          <Card label="MAE / mean output" value={m.nmae_pct ? m.nmae_pct.toFixed(1) : "–"} unit="%" />
        </div>

        {m.bias != null && (
          <div className="finding">
            <b>Key finding:</b> over the selected period, the forecast was on
            average <b>{fmt(Math.abs(m.bias))} MW {m.bias >= 0 ? "higher" : "lower"}</b>{" "}
            than the actual generation
            {biasPct != null && <> ({Math.abs(biasPct).toFixed(1)}% of average output)</>}
            . Relying on the forecast alone would{" "}
            {m.bias >= 0
              ? "have over-estimated wind, so you would under-buy."
              : "have under-estimated wind, so you would over-buy."}{" "}
            This is a measured result for this period only.
          </div>
        )}

        {error && <p className="err">{error}</p>}
        {loading && <p className="note">Loading…</p>}

        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={series.points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="t" tickFormatter={(t) => t.slice(5, 10)} minTickGap={50} />
            <YAxis unit=" MW" width={90} tickFormatter={fmt} />
            <Tooltip labelFormatter={shortTime} formatter={(v) => fmt(v) + " MW"} />
            <Legend />
            <Line dataKey="actual" name="Actual" stroke="#111" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <Line dataKey="forecast" name="Forecast" stroke="#1f5fbf" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* ---------- Section 3 ---------- */}
      <section className="panel grid2">
        <div>
          <h3>Error vs how far ahead the forecast was made</h3>
          <p className="note">The further ahead the forecast, the larger the typical miss.</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={byHorizon}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="horizon_h" unit="h" />
              <YAxis unit=" MW" width={90} tickFormatter={fmt} />
              <Tooltip formatter={(v) => fmt(v) + " MW"} />
              <Legend />
              <Bar dataKey="mae" name="MAE" fill="#1f5fbf" />
              <Bar dataKey="p90_abs_error" name="P90" fill="#e08a1e" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h3>Error by hour of day (UTC)</h3>
          <p className="note">Uses the mode and settings chosen above.</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={byHour}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis unit=" MW" width={90} tickFormatter={fmt} />
              <Tooltip formatter={(v) => fmt(v) + " MW"} />
              <Bar dataKey="mae" name="MAE" fill="#2e9d6b" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ---------- Section 4 ---------- */}
      <section className="panel">
        <h2>3. Is the error bigger when the forecast says it will be windy?</h2>
        <p className="sub">
          Average forecast error, grouped by how much wind was forecast (the
          number of hours in each group is shown in brackets). Above zero
          means the forecast was too high. The forecast level is known at
          decision time, so this can be used when planning.
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={levelData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis unit=" MW" width={90} tickFormatter={fmt} />
            <Tooltip formatter={(v) => fmt(v) + " MW"} />
            <Legend />
            <ReferenceLine y={0} stroke="#111" />
            <Bar dataKey="bias" name="Average error (bias)" fill="#e08a1e" />
            <Bar dataKey="mae" name="Average miss (MAE)" fill="#1f5fbf" />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* ---------- Method ---------- */}
      <section className="panel">
        <h2>Method &amp; assumptions</h2>
        <ul className="plain">
          <li>Data: Elexon BMRS. FUELHH gives the actual wind generation (fuel type WIND, 30-minute values). WINDFOR gives wind forecasts with the time each forecast was published.</li>
          <li>Scope: purchase decisions made 1–31 January 2026 for delivery the next day (2 January – 1 February). National wind only.</li>
          <li>Decision time: 09:00 UTC on the day before delivery is an assumption, and you can change it above. Only forecasts published at or before that time are used. Later forecasts are ignored.</li>
          <li>Forecasts are published hourly, so errors are compared on those hourly times ({fmt(headline.n)} hours).</li>
          <li>Error = forecast minus actual. Positive means the forecast was too high.</li>
          <li>Limitations: one month of data only; the likely range uses the whole month&apos;s P90 error; the cause of the bias has not been established.</li>
        </ul>
      </section>
    </div>
  );
}