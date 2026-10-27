import React, { useEffect, useState } from "react";
import { ResponsiveContainer, ComposedChart, Line, Area, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

const f0 = (x) => (x == null ? "–" : Math.round(x).toLocaleString());
const f1 = (x) => (x == null ? "–" : x.toFixed(1));
const api = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText); return r.json(); };
const hhmm = (iso) => new Date(iso).toLocaleString("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

const INFO = {
  cutoff: "The time on the day BEFORE delivery when your desk must finalise the day-ahead purchase. Only forecasts published before this time are used. Change it to match your desk's real deadline.",
  day: "The day the electricity will actually be delivered. You buy it the day before.",
  pct: "How cautious you want to be. P95 means: in 95% of past days the forecast over-estimated wind by less than the buffer shown. Higher = safer but you buy more thermal power.",
  latest: "When the newest forecast you could see at your cutoff was created by Elexon (publishTime).",
  avg: "Average forecast wind power for the delivery day, in megawatts (MW).",
  minmax: "Lowest and highest forecast wind power during the day.",
  buffer: "How many MW the forecast has over-estimated wind, at the chosen risk level, using only earlier days. Subtract it from the forecast for a cautious wind figure.",
  priormae: "Mean Absolute Error on earlier days: the typical size of the miss, ignoring direction.",
  mae: "Mean Absolute Error: average size of the forecast miss in MW. Easy to read: 'usually off by about this much'.",
  rmse: "Root Mean Square Error: like MAE but punishes big misses more. Higher than MAE means some large misses exist.",
  bias: "Average of (forecast − actual). Positive = forecast tends to over-estimate wind (risk of buying too little). Negative = under-estimates.",
  mape: "Mean Absolute Percentage Error: the average miss as a % of actual wind.",
  p95: "On the worst 5% of half-hours the forecast was too high by at least this many MW.",
  p05: "On 5% of half-hours the forecast was too LOW by at least this many MW (negative number).",
  lead: "Lead time = how many hours before delivery the forecast was made. Forecasts made closer to delivery are usually more accurate.",
  compare: "Compares your day-ahead forecast with a later one made at least 4 hours before delivery, on exactly the same half-hours.",
  worst: "Days where the forecast missed by the most. Good days to keep extra buffer.",
  hour: "Does accuracy depend on the time of day? Hours are London time.",
  age: "How old the newest forecast was at your cutoff. Smaller is better: a fresher forecast is usually more accurate.",
  runs: "How many separate forecast versions Elexon had published for this delivery day by your cutoff. The app picks the newest for each half-hour.",
  dq: "Checks that the downloaded data is complete and sensible before you trust any numbers.",
};
const Info = ({ k }) => <span className="info" tabIndex={0}>i<span className="tip">{INFO[k]}</span></span>;
const Kpi = ({ k, label, value, unit }) => <div className="kpi"><span>{label} {k && <Info k={k} />}</span><b>{value}</b><small>{unit}</small></div>;
const H = ({ k, children }) => <h3>{children} {k && <Info k={k} />}</h3>;
const Bars = ({ title, k, data, y, x, c }) => (
  <div className="card"><H k={k}>{title}</H><ResponsiveContainer width="100%" height={260}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={x} fontSize={12} /><YAxis fontSize={12} width={70} /><Tooltip formatter={(v) => f0(v) + " MW"} /><Bar dataKey={y} fill={c} /></BarChart></ResponsiveContainer></div>);

function Forecast({ days, cutoff }) {
  const [day, setDay] = useState("2026-01-15"); const [pct, setPct] = useState(95); const [d, setD] = useState(null); const [err, setErr] = useState(null);
  useEffect(() => { setD(null); setErr(null); api(`/api/forecast?date=${day}&cutoff_hour=${cutoff}&percentile=${pct / 100}`).then(setD).catch((e) => setErr(e.message)); }, [day, cutoff, pct]);
  const s = d?.summary;
  const rows = d?.series.map((r) => ({ ...r, t: hhmm(r.startTime), band: r.conservative != null ? [r.conservative, r.forecast] : null }));
  const mean = (k) => { const v = d.series.map((r) => r[k]).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
  return (<>
    <div className="bar">
      <label><span>Delivery day <Info k="day" /></span><select value={day} onChange={(e) => setDay(e.target.value)}>{days.map((x) => <option key={x}>{x}</option>)}</select></label>
      <label><span>Risk level: P{pct} <Info k="pct" /></span><input type="range" min="50" max="99" value={pct} onChange={(e) => setPct(+e.target.value)} /></label>
      <a href={`/api/forecast.csv?date=${day}&cutoff_hour=${cutoff}&percentile=${pct / 100}`}>⬇ Export CSV</a></div>
    {err && <p className="warn">{err}</p>}{!d && !err && <p>Loading…</p>}
    {d && <>
      <div className="say"><b>Decision point:</b> you buy on <b>{hhmm(s.cutoff)}</b> for delivery on <b>{day}</b>. <b>In plain English:</b> by your cutoff, the latest forecast for {day} says wind averages <b>{f0(s.avg_mw)} MW</b>. Being cautious at P{pct}, assume about <b>{f0(mean("conservative"))} MW</b> instead
        {s.buffer_mw != null && <> (that is {f0(s.buffer_mw)} MW less, based on {s.history_days} earlier days)</>}, and plan thermal purchases to cover the gap. In hindsight, wind actually averaged <b>{f0(mean("actual"))} MW</b>.</div>
      <div className="kpis">
        <Kpi k="latest" label="Latest forecast available" value={s.latest_publish ? hhmm(s.latest_publish) : "–"} unit={`cutoff ${hhmm(s.cutoff)}`} />
        <Kpi k="age" label="Forecast age at cutoff" value={f1(s.age_h)} unit="hours old" />
        <Kpi k="runs" label="Forecast versions seen" value={s.n_revisions} unit="published before cutoff" />
        <Kpi k="avg" label="Average forecast wind" value={f0(s.avg_mw)} unit="MW" />
        <Kpi k="minmax" label="Min / Max forecast" value={`${f0(s.min_mw)} / ${f0(s.max_mw)}`} unit="MW" />
        <Kpi k="buffer" label={`Safety buffer (P${pct})`} value={f0(s.buffer_mw)} unit="MW" />
        <Kpi k="priormae" label="Typical miss on prior days" value={f0(s.history?.mae)} unit="MW (MAE)" /></div>
      <div className="card"><H>Forecast vs actual wind, half-hourly</H>
        <ResponsiveContainer width="100%" height={420}><ComposedChart data={rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" minTickGap={50} fontSize={12} /><YAxis unit=" MW" fontSize={12} width={85} /><Tooltip /><Legend />
          <Area dataKey="band" name={`Risk band (forecast − P${pct} buffer)`} fill="#e9892f" stroke="none" fillOpacity={0.3} />
          <Line dataKey="forecast" name="Forecast known at cutoff" stroke="#0b6fa4" dot={false} strokeWidth={2.5} />
          <Line dataKey="actual" name="Actual (known only afterwards)" stroke="#2a9d55" dot={false} strokeWidth={2.5} /></ComposedChart></ResponsiveContainer>
        <p className="note">Blue is what you could see when buying. Green is what really happened. The orange band is the cautious range: the lower edge is the wind you could count on at your chosen risk level.</p>
        <details><summary>Show half-hourly numbers</summary><table><thead><tr><th>Time (London)</th><th>Forecast MW</th><th>Cautious MW</th><th>Actual MW</th></tr></thead><tbody>
          {d.series.map((r) => <tr key={r.startTime}><td>{hhmm(r.startTime)}</td><td>{f0(r.forecast)}</td><td>{f0(r.conservative)}</td><td>{f0(r.actual)}</td></tr>)}</tbody></table></details></div></>}
  </>);
}

function Accuracy({ cutoff }) {
  const [a, setA] = useState(null); const [err, setErr] = useState(null);
  useEffect(() => { setA(null); api(`/api/accuracy?cutoff_hour=${cutoff}`).then(setA).catch((e) => setErr(e.message)); }, [cutoff]);
  if (err) return <p className="warn">{err}</p>; if (!a) return <p>Loading…</p>;
  const o = a.overall;
  return (<>
    <div className="say"><b>In plain English:</b> across {o.n.toLocaleString()} half-hours of January, the day-ahead forecast was typically off by <b>{f0(o.mae)} MW</b> ({f1(o.mape)}% of actual wind). On average it <b>{o.bias > 0 ? "over" : "under"}-estimated</b> wind by {f0(Math.abs(o.bias))} MW, and on the worst 5% of half-hours it was too high by {f0(o.p95)} MW or more.</div>
    <div className="kpis">
      <Kpi k="mae" label="MAE" value={f0(o.mae)} unit="MW" /><Kpi k="rmse" label="RMSE" value={f0(o.rmse)} unit="MW" />
      <Kpi k="bias" label="Bias" value={f0(o.bias)} unit="MW (+ = over-forecast)" /><Kpi k="mape" label="MAPE" value={f1(o.mape) + "%"} unit="of actual" />
      <Kpi k="p95" label="Worst 5% over-forecast" value={f0(o.p95)} unit="MW" /><Kpi k="p05" label="Worst 5% under-forecast" value={f0(o.p05)} unit="MW" /></div>
    <div className="grid2"><Bars title="Error by delivery day (MAE)" k="mae" data={a.daily} y="mae" x="day" c="#0b6fa4" /><Bars title="Error by hour of day (MAE)" k="hour" data={a.hourly} y="mae" x="hour" c="#2a9d8f" /></div>
    <div className="grid2"><Bars title="Error by hours-ahead (lead time, last bar = 42h+)" k="lead" data={a.horizon} y="mae" x="lead_from_h" c="#e9892f" />
      {a.compare?.later?.n > 0 && <div className="card"><H k="compare">Does waiting for a later forecast help?</H>
        <table><thead><tr><th>Forecast used</th><th>MAE</th><th>RMSE</th><th>Bias</th></tr></thead><tbody>
          <tr><td>Day-ahead (your cutoff)</td><td>{f0(a.compare.decision.mae)}</td><td>{f0(a.compare.decision.rmse)}</td><td>{f0(a.compare.decision.bias)}</td></tr>
          <tr><td>{a.compare.lead_h}+ hours before delivery</td><td>{f0(a.compare.later.mae)}</td><td>{f0(a.compare.later.rmse)}</td><td>{f0(a.compare.later.bias)}</td></tr></tbody></table>
        <p className="note">All figures in MW.</p></div>}</div>
    <div className="card"><H k="worst">Hardest days to forecast</H>
      <table><thead><tr><th>Delivery day</th><th>MAE (MW)</th><th>Bias (MW)</th><th>Worst 5% over-forecast (MW)</th></tr></thead><tbody>
        {a.worst_days.map((w) => <tr key={w.day}><td>{w.day}</td><td>{f0(w.mae)}</td><td>{f0(w.bias)}</td><td>{f0(w.p95)}</td></tr>)}</tbody></table>
      <p><a href={`/api/accuracy.csv?cutoff_hour=${cutoff}`}>⬇ Export daily accuracy CSV</a></p></div>
  </>);
}

function Quality() {
  const [q, setQ] = useState(null); const [err, setErr] = useState(null);
  useEffect(() => { api("/api/data-quality").then(setQ).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="warn">{err}</p>; if (!q) return <p>Loading…</p>;
  const chk = [
    ["Actual wind complete (32 days × 48 half-hours)", q.actual_rows === q.expected_actual_rows, `${q.actual_rows} of ${q.expected_actual_rows} rows`],
    ["No missing actual values", q.actual_missing === 0, `${q.actual_missing} missing`],
    ["Forecasts downloaded", q.forecast_rows > 0, `${q.forecast_rows.toLocaleString()} rows from ${q.forecast_publishes} forecast runs`],
    ["Every delivery day has a decision-time forecast (cutoff 09:00)", q.days_covered === q.total_days, `${q.days_covered} of ${q.total_days} days`],
    ["Every decision-time forecast was published before its cutoff", q.cutoff_violations === 0, `${q.cutoff_violations} violations`]];
  return (<>
    <div className="card"><H k="dq">Automatic data checks</H>
      <table><tbody>{chk.map(([n, ok, d]) => <tr key={n}><td>{n}</td><td>{d}</td><td className={ok ? "ok" : "bad"}>{ok ? "✓ PASS" : "✗ CHECK"}</td></tr>)}</tbody></table></div>
    <div className="say"><b>ℹ Note on the data:</b> {q.late_rows.toLocaleString()} of the {q.forecast_rows.toLocaleString()} forecast rows ({f1(q.late_pct)}%) were published <i>after</i> the half-hour they predict (a negative lead time). They could never have been seen when buying a day ahead, so they are excluded from the decision-time view and from the lead-time analysis. They do not affect any result in this portal.</div>
    <div className="card"><H>Data summary</H><table><tbody>
      <tr><td>Actuals period</td><td>{hhmm(q.actual_from)} → {hhmm(q.actual_to)}</td></tr>
      <tr><td>Actual wind min / mean / max</td><td>{f0(q.actual_min)} / {f0(q.actual_mean)} / {f0(q.actual_max)} MW</td></tr>
      <tr><td>Forecasts published</td><td>{hhmm(q.publish_from)} → {hhmm(q.publish_to)}</td></tr>
      <tr><td>Forecast mean (all lead times)</td><td>{f0(q.forecast_mean)} MW</td></tr>
      <tr><td>Lead time min / median / max</td><td>{f1(q.lead_min)} / {f1(q.lead_median)} / {f1(q.lead_max)} hours</td></tr></tbody></table></div></>);
}

const GLOSS = [["Negative lead time","A forecast whose publish time is after the half-hour it predicts. These exist in the raw data and are excluded."],["Day-ahead market", "Electricity bought the day before delivery. Your desk must decide how much to buy before the market closes."], ["Wind forecast (WINDFOR)", "Elexon's prediction of national wind power. New forecasts are published many times a day."], ["Actual wind (FUELHH)", "Metered wind generation, in half-hour blocks. Only known after the fact."], ["MW", "Megawatt, a unit of power. 1,000 MW powers roughly a million homes."], ["Publish time", "When a forecast was created. We only use forecasts created before your cutoff."], ["Error", "Forecast minus actual. Positive means the forecast was too optimistic about wind."], ["Percentile (P95)", "A value that 95% of cases stay below. Used to size a safety buffer."], ["Look-ahead", "Cheating by using information from the future. The app never does this."]];
function Guide() {
  return (<>
    <div className="card"><h3>What problem does this solve?</h3><p className="note">Your desk buys electricity the day before delivery. Wind is free but unpredictable, so you buy less from thermal plants when wind is high. That means you are betting on a forecast. This portal shows (1) the exact forecast you had when you decided and (2) how wrong such forecasts have been, so you can add a sensible safety margin.</p></div>
    <div className="card"><h3>How to use it in 3 steps</h3><ol className="note"><li>Set your decision cutoff (top of the page) to match your real deadline.</li><li>On <b>Forecast</b>, pick a delivery day and a risk level to see forecast wind and a cautious wind number.</li><li>On <b>Accuracy</b>, see how large and in which direction the forecast errors are, and which days and hours are riskiest.</li></ol></div>
    <div className="card"><h3>Glossary</h3><dl>{GLOSS.map(([t, d]) => <React.Fragment key={t}><dt>{t}</dt><dd>{d}</dd></React.Fragment>)}</dl></div></>);
}

export default function App() {
  const [tab, setTab] = useState("f"); const [days, setDays] = useState([]); const [cutoff, setCutoff] = useState(9); const [ready, setReady] = useState(false);
  useEffect(() => { api("/api/days").then(setDays); const i = setInterval(() => api("/api/health").then((h) => { setReady(h.ready); if (h.ready) clearInterval(i); }), 2000); return () => clearInterval(i); }, []);
  const T = [["f", "Forecast at decision time"], ["a", "Forecast accuracy"], ["q", "Data quality"], ["g", "Guide & glossary"]];
  return (<><header><h1>🌬️ UK Wind Generation – Day-Ahead Forecast Analyser</h1><p>Elexon BMRS · WINDFOR forecasts vs FUELHH actuals · purchase decisions for January 2026</p>
    <nav>{T.map(([k, n]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{n}</button>)}</nav></header>
    <main>
      {(tab === "f" || tab === "a") && <div className="bar"><label><span>Decision cutoff on the day before (London hour) <Info k="cutoff" /></span><input type="number" min="0" max="23" value={cutoff} onChange={(e) => setCutoff(Math.min(23, Math.max(0, +e.target.value)))} /></label>{!ready && <span className="note">Loading Elexon data (first start only, about a minute)…</span>}</div>}
      {tab === "f" && <Forecast days={days} cutoff={cutoff} />}{tab === "a" && <Accuracy cutoff={cutoff} />}{tab === "q" && <Quality />}{tab === "g" && <Guide />}
    </main><footer>Data: Elexon Insights Solution (BMRS). Built as a pilot for a UK energy utility's day-ahead desk.</footer></>);
}
