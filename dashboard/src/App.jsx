import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell
} from "recharts";

// ─── CONSTANTS ────────────────────────────────────────────────────────────────
const STARTING_BALANCE  = 200_000;
const DAILY_GATE_PCT    = 0.018;   // 1.8% internal Guardian trigger
const MAX_GATE_PCT      = 0.035;   // 3.5% max internal trigger
const CONSISTENCY_LIMIT = 0.15;    // 15% FP consistency rule
const MIN_HOLD_SECS     = 90;      // HFT compliance floor

// ─── CSV PARSER ───────────────────────────────────────────────────────────────
function parseCSV(text) {
  const lines = text.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map(h => h.trim());
  return lines.slice(1).map(line => {
    const vals = line.split(",");
    const row = {};
    headers.forEach((h, i) => { row[h] = vals[i]?.trim() ?? ""; });
    return {
      timestamp:  row["Timestamp"] || row["timestamp"] || "",
      direction:  row["Direction"] || row["direction"] || "",
      lots:       parseFloat(row["Lots"] || row["lots"] || 0),
      fillPrice:  parseFloat(row["Fill_Price"] || row["fill_price"] || 0),
      spread:     parseFloat(row["Spread_pts"] || row["spread_pts"] || 0),
      slippage:   parseFloat(row["Slippage_pts"] || row["slippage_pts"] || 0),
      commission: parseFloat(row["Commission"] || row["commission"] || 0),
      pnl:        parseFloat(row["PnL"] || row["pnl"] || 0),
      equity:     parseFloat(row["Equity"] || row["equity"] || 0),
    };
  }).filter(r => !isNaN(r.equity) && r.equity > 0);
}

// ─── SYNTHETIC DEMO DATA ──────────────────────────────────────────────────────
function generateDemoData() {
  const trades = [];
  let equity = STARTING_BALANCE;
  let basePrice = 20150;
  const now = Date.now();

  for (let i = 0; i < 41; i++) {
    const holdSecs = 90 + Math.random() * 180;
    const dir = Math.random() > 0.45 ? "LONG" : "SHORT";
    const pnl = (Math.random() - 0.35) * 200;
    equity += pnl;
    basePrice += (Math.random() - 0.5) * 20;
    const ts = new Date(now - (41 - i) * holdSecs * 1000);
    trades.push({
      timestamp:  ts.toISOString().replace("T", " ").slice(0, 19),
      direction:  dir,
      lots:       0.2,
      fillPrice:  parseFloat(basePrice.toFixed(2)),
      spread:     1.20,
      slippage:   0.30,
      commission: 0.60,
      pnl:        parseFloat(pnl.toFixed(2)),
      equity:     parseFloat(equity.toFixed(2)),
      holdSecs:   parseFloat(holdSecs.toFixed(1)),
    });
  }
  return trades;
}

// ─── DERIVED METRICS ──────────────────────────────────────────────────────────
function computeMetrics(trades) {
  if (!trades.length) return null;

  const last  = trades[trades.length - 1];
  const netPnl = last.equity - STARTING_BALANCE;

  // Daily grouping
  const byDay = {};
  trades.forEach(t => {
    const day = t.timestamp.slice(0, 10);
    if (!byDay[day]) byDay[day] = 0;
    byDay[day] += t.pnl;
  });
  const dayPnls   = Object.values(byDay);
  const todayKey  = Object.keys(byDay).slice(-1)[0];
  const todayPnl  = byDay[todayKey] || 0;
  const dayOpen   = last.equity - todayPnl;
  const dailyDD   = Math.max(0, dayOpen - last.equity) / STARTING_BALANCE;

  // Consistency: max single day / total profit
  const totalPositivePnl = dayPnls.filter(p => p > 0).reduce((a, b) => a + b, 0);
  const maxDay = Math.max(...dayPnls.filter(p => p > 0), 0);
  const consistency = totalPositivePnl > 0 ? maxDay / totalPositivePnl : 0;

  // Risk metrics
  let peak = STARTING_BALANCE;
  let maxDD = 0;
  trades.forEach(t => {
    if (t.equity > peak) peak = t.equity;
    const dd = (peak - t.equity) / STARTING_BALANCE;
    if (dd > maxDD) maxDD = dd;
  });

  // Win/loss
  const winners = trades.filter(t => t.pnl > 0);
  const losers  = trades.filter(t => t.pnl < 0);
  const grossW  = winners.reduce((a, t) => a + t.pnl, 0);
  const grossL  = Math.abs(losers.reduce((a, t) => a + t.pnl, 0));

  // Hold times
  const holdTimes = trades.map((t, i) => {
    if (i === 0) return 120;
    const a = new Date(trades[i - 1].timestamp).getTime();
    const b = new Date(t.timestamp).getTime();
    return Math.round((b - a) / 1000);
  });
  const avgHold = holdTimes.reduce((a, b) => a + b, 0) / holdTimes.length;
  const hftFlags = holdTimes.filter(h => h < MIN_HOLD_SECS).length;

  // Sharpe proxy (per-trade)
  const pnls = trades.map(t => t.pnl);
  const mean = pnls.reduce((a, b) => a + b, 0) / pnls.length;
  const std  = Math.sqrt(pnls.reduce((a, b) => a + (b - mean) ** 2, 0) / pnls.length);
  const dsideVals = pnls.filter(p => p < 0);
  const dstd = dsideVals.length
    ? Math.sqrt(dsideVals.reduce((a, b) => a + b ** 2, 0) / dsideVals.length) : 1e-8;
  const sharpe  = std > 0 ? (mean / std) * Math.sqrt(pnls.length) : 0;
  const sortino = dstd > 0 ? (mean / dstd) * Math.sqrt(pnls.length) : 0;

  // Wyckoff phase heuristic
  const recent = trades.slice(-8);
  const recentPnl = recent.reduce((a, t) => a + t.pnl, 0);
  const recentDir = recent.filter(t => t.direction === "LONG").length / recent.length;
  let wyckoffPhase = "Consolidation (Awaiting Structure)";
  if (recentPnl > 200 && recentDir > 0.65) wyckoffPhase = "Markup (Accumulation Confirmed)";
  else if (recentPnl > 200 && recentDir < 0.35) wyckoffPhase = "Markdown (Distribution Detected)";
  else if (recentPnl < -100) wyckoffPhase = "Spring Detected (Potential Reversal)";
  else if (Math.abs(recentPnl) < 50) wyckoffPhase = "Ranging (No Structural Edge)";

  return {
    equity: last.equity,
    netPnl,
    netPct:      (netPnl / STARTING_BALANCE) * 100,
    dailyDD,
    maxDD,
    consistency,
    tradeCount:  trades.length,
    winRate:     winners.length / trades.length,
    profitFactor: grossL > 0 ? grossW / grossL : Infinity,
    expectancy:  mean,
    sharpe,
    sortino,
    avgHold,
    hftFlags,
    holdTimes,
    wyckoffPhase,
  };
}

// ─── THEME CONSTANTS ──────────────────────────────────────────────────────────
const COLORS = {
  bg: "#000000",
  panel: "#1C1C1E",
  border: "#2C2C2E",
  textMain: "#FFFFFF",
  textMuted: "#8E8E93",
  primary: "#0A84FF",
  secondary: "#30D158",
  warning: "#FF9F0A",
  danger: "#FF453A",
  profit: "#EBEBF5",
  loss: "#636366",
  grid: "#2C2C2E"
};

const FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

// ─── CUSTOM TOOLTIP ───────────────────────────────────────────────────────────
const AppleTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(28, 28, 30, 0.95)",
      border: `1px solid ${COLORS.border}`,
      borderRadius: "8px",
      padding: "12px",
      fontFamily: FONT,
      fontSize: "12px",
      color: COLORS.textMain,
      backdropFilter: "blur(10px)",
      WebkitBackdropFilter: "blur(10px)"
    }}>
      <div style={{ color: COLORS.textMuted, marginBottom: "6px", fontWeight: 500 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: "12px", margin: "2px 0" }}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span style={{ fontWeight: 600 }}>{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</span>
        </div>
      ))}
    </div>
  );
};

// ─── STAT BLOCK ───────────────────────────────────────────────────────────────
const Stat = ({ label, value, sub, color = COLORS.textMain }) => (
  <div style={{ display: "flex", flexDirection: "column" }}>
    <div style={{
      fontFamily: FONT,
      fontSize: "11px",
      fontWeight: 500,
      color: COLORS.textMuted,
      marginBottom: "4px",
    }}>{label}</div>
    <div style={{
      fontFamily: FONT,
      fontSize: "24px",
      fontWeight: 600,
      color: color,
      letterSpacing: "-0.5px"
    }}>{value}</div>
    {sub && <div style={{
      fontFamily: FONT,
      fontSize: "11px",
      color: COLORS.textMuted,
      marginTop: "2px",
    }}>{sub}</div>}
  </div>
);

// ─── PROGRESS BAR ─────────────────────────────────────────────────────────────
const ProgressBar = ({ value, max, label }) => {
  const pct = Math.min((value / max) * 100, 100);
  const isWarn = pct > 80;
  return (
    <div style={{ marginBottom: "12px" }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        fontFamily: FONT,
        fontSize: "11px",
        color: COLORS.textMuted,
        marginBottom: "6px",
      }}>
        <span>{label}</span>
        <span>{(value * 100).toFixed(2)}% / {(max * 100).toFixed(1)}%</span>
      </div>
      <div style={{
        background: COLORS.bg,
        height: "6px",
        borderRadius: "3px",
        overflow: "hidden"
      }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          background: isWarn ? COLORS.warning : COLORS.primary,
          borderRadius: "3px"
        }} />
      </div>
    </div>
  );
};

// ─── MAIN APP COMPONENT ───────────────────────────────────────────────────────
export default function App() {
  const [trades, setTrades] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [demoMode, setDemoMode] = useState(true);
  const fileRef = useRef();

  useEffect(() => {
    const demo = generateDemoData();
    setTrades(demo);
    setMetrics(computeMetrics(demo));
  }, []);

  const onFileLoad = useCallback(e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      const parsed = parseCSV(ev.target.result);
      if (parsed.length) {
        setTrades(parsed);
        setMetrics(computeMetrics(parsed));
        setDemoMode(false);
      }
    };
    reader.readAsText(file);
  }, []);

  const equityCurve = [
    { t: "Start", equity: STARTING_BALANCE },
    ...trades.map((tr, i) => ({
      t: tr.timestamp.slice(11, 16) || `T${i}`,
      equity: tr.equity,
    }))
  ];

  const pnlBars = trades.slice(-50).map((tr, i) => ({
    i: i + 1,
    pnl: tr.pnl,
    friction: -(tr.commission + (tr.spread + tr.slippage) * tr.lots * 100),
  }));

  const holdScatter = (metrics?.holdTimes || []).map((h, i) => ({
    trade: i + 1,
    hold: h
  }));

  const m = metrics;

  return (
    <div style={{
      background: COLORS.bg,
      minHeight: "100vh",
      color: COLORS.textMain,
      fontFamily: FONT,
      padding: "24px",
      boxSizing: "border-box"
    }}>
      {/* Header */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "32px",
        padding: "16px 24px",
        background: COLORS.panel,
        borderRadius: "16px",
      }}>
        <div>
          <div style={{ fontSize: "20px", fontWeight: 600, letterSpacing: "-0.5px" }}>Kessler Capital</div>
          <div style={{ fontSize: "12px", color: COLORS.textMuted, marginTop: "2px" }}>Institutional Operations Engine</div>
        </div>
        
        <div style={{ display: "flex", gap: "32px", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "11px", color: COLORS.textMuted, textAlign: "right" }}>Account Value</div>
            <div style={{ fontSize: "24px", fontWeight: 600 }}>
              ${m ? m.equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "200,000.00"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "11px", color: COLORS.textMuted, textAlign: "right" }}>Net Return</div>
            <div style={{ fontSize: "18px", fontWeight: 500, color: m?.netPnl >= 0 ? COLORS.textMain : COLORS.loss }}>
              {m ? `${m.netPnl >= 0 ? "+" : ""}$${m.netPnl.toFixed(2)} (${m.netPct.toFixed(2)}%)` : "—"}
            </div>
          </div>
          
          <div style={{ borderLeft: `1px solid ${COLORS.border}`, paddingLeft: "32px" }}>
            <input ref={fileRef} type="file" accept=".csv" onChange={onFileLoad} style={{ display: "none" }} />
            <button 
              onClick={() => fileRef.current?.click()}
              style={{
                background: COLORS.textMain,
                color: COLORS.bg,
                border: "none",
                borderRadius: "20px",
                padding: "8px 16px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {demoMode ? "Load Data" : "Refresh"}
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px" }}>
        
        {/* Left Column (Charts) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* Equity Chart */}
          <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px" }}>
            <div style={{ marginBottom: "16px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Performance History</div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={equityCurve}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="t" tick={{ fill: COLORS.textMuted, fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={30} />
                <YAxis domain={["auto", "auto"]} tick={{ fill: COLORS.textMuted, fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} width={50} />
                <Tooltip content={<AppleTooltip />} cursor={{ stroke: COLORS.border }} />
                <Line type="monotone" dataKey="equity" name="Equity" stroke={COLORS.primary} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.primary }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
            {/* PnL Bar Chart */}
            <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px" }}>
              <div style={{ marginBottom: "16px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Recent Realized Returns</div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={pnlBars}>
                  <XAxis dataKey="i" hide />
                  <Tooltip content={<AppleTooltip />} cursor={{ fill: "transparent" }} />
                  <ReferenceLine y={0} stroke={COLORS.border} />
                  <Bar dataKey="pnl" name="Net PnL" radius={[2, 2, 2, 2]} maxBarSize={8}>
                    {pnlBars.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? COLORS.profit : COLORS.loss} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Hold Times */}
            <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px" }}>
              <div style={{ marginBottom: "16px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Execution Duration</div>
              <ResponsiveContainer width="100%" height={180}>
                <ScatterChart>
                  <XAxis dataKey="trade" hide />
                  <YAxis dataKey="hold" tick={{ fill: COLORS.textMuted, fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                  <Tooltip content={<AppleTooltip />} cursor={{ stroke: COLORS.border, strokeDasharray: "4 4" }} />
                  <ReferenceLine y={MIN_HOLD_SECS} stroke={COLORS.warning} strokeDasharray="3 3" />
                  <Scatter data={holdScatter} name="Seconds">
                    {holdScatter.map((entry, i) => (
                      <Cell key={i} fill={entry.hold < MIN_HOLD_SECS ? COLORS.warning : COLORS.primary} fillOpacity={0.6} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Column (Metrics & Telemetry) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px" }}>
            <div style={{ marginBottom: "20px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Risk Parameters</div>
            <ProgressBar value={m?.dailyDD || 0} max={DAILY_GATE_PCT} label="Intraday Drawdown" />
            <ProgressBar value={m?.consistency || 0} max={CONSISTENCY_LIMIT} label="Concentration Index" />
          </div>

          <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px" }}>
            <div style={{ marginBottom: "20px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Market Structure</div>
            <div style={{ fontSize: "14px", fontWeight: 500, color: COLORS.textMain, lineHeight: 1.5 }}>
              {m?.wyckoffPhase || "Awaiting Data"}
            </div>
          </div>

          <div style={{ background: COLORS.panel, padding: "24px", borderRadius: "16px", flex: 1 }}>
            <div style={{ marginBottom: "20px", fontSize: "14px", fontWeight: 500, color: COLORS.textMuted }}>Key Statistics</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <Stat label="Total Volume" value={m ? m.tradeCount : "—"} sub="Round-trip executions" />
              <Stat label="Win Ratio" value={m ? `${(m.winRate * 100).toFixed(1)}%` : "—"} />
              <Stat label="Profit Factor" value={m ? m.profitFactor.toFixed(2) : "—"} />
              <Stat label="Avg Hold Time" value={m ? `${m.avgHold.toFixed(0)}s` : "—"} color={m && m.hftFlags > 0 ? COLORS.warning : COLORS.textMain} />
              <Stat label="Sharpe (Trade)" value={m ? m.sharpe.toFixed(2) : "—"} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
