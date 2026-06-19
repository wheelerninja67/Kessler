'use strict';

/* ============================================================
   KESSLER // OPS — APP LOGIC
   No frameworks. Direct DOM patching only — table rows and feed
   lines are inserted/removed individually, never re-rendered in
   bulk.
   ============================================================ */

const CONFIG = {
  // Flip to false once your FastAPI backend is live. The WSClient
  // below is fully wired and ready — nothing else needs to change.
  USE_MOCK: true,

  WS_URL: 'ws://localhost:8000/ws/kessler',
  WS_RECONNECT_MIN_MS: 1000,
  WS_RECONNECT_MAX_MS: 10000,

  MOCK_TICK_MS: 50,           // HFT TICK RATE: 20 ticks per second
  MOCK_TRADE_CHANCE: 0.6,     // 60% chance to enter a trade instantly
  MOCK_LATENCY_BASE: 18,
  MOCK_VOLATILITY: 3.5,       // Higher volatility for aggressive chart movement

  MAX_FEED_LINES: 160,
  MAX_LOG_ROWS: 120,

  START_EQUITY: 100000,
  DAILY_DD_LIMIT: 5.0,
  DAILY_DD_WARN: 4.0,
};

/* ============================================================
   DOM CACHE
   ============================================================ */

const dom = {
  equity:     document.getElementById('val-equity'),
  ddMetric:   document.getElementById('metric-dd'),
  dd:         document.getElementById('val-dd'),
  statusDot:  document.getElementById('status-dot'),
  valStatus:  document.getElementById('status-text'),
  latency:    document.getElementById('val-latency'),
  clock:      document.getElementById('clock'),
  feed:       document.getElementById('feed'),
  feedRate:   document.getElementById('feed-rate'),
  chartPrice: document.getElementById('chart-price'),
  logBody:    document.getElementById('log-body'),
  logCount:   document.getElementById('log-count'),
};

/* ============================================================
   STATE
   ============================================================ */

const state = {
  equity: CONFIG.START_EQUITY,
  dayStartEquity: CONFIG.START_EQUITY,
  tradeCount: 0,
  chart: null,
  lineSeries: null,
  chartTime: Math.floor(Date.now() / 1000),
};

/* ============================================================
   FORMAT HELPERS
   ============================================================ */

const fmtUSD = (n) =>
  '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtPct = (n, digits = 1) => (n >= 0 ? '+' : '') + n.toFixed(digits) + '%';

const fmtPrice = (n) => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtDuration = (sec) => {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m${String(s).padStart(2, '0')}s`;
};

const fmtClockTime = (d) =>
  d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');

/* ============================================================
   RENDER — KILLSWITCH MATRIX
   ============================================================ */

function renderEquity(equity) {
  const prev = state.equity;
  state.equity = equity;
  dom.equity.textContent = fmtUSD(equity);

  dom.equity.classList.remove('flash-up', 'flash-down');
  if (equity > prev) dom.equity.classList.add('flash-up');
  if (equity < prev) dom.equity.classList.add('flash-down');
  // browsers coalesce same-frame class churn — defer the clear one frame
  requestAnimationFrame(() => {
    setTimeout(() => dom.equity.classList.remove('flash-up', 'flash-down'), 600);
  });
}

function renderDrawdown(equity) {
  const ddPct = ((state.dayStartEquity - equity) / state.dayStartEquity) * 100;
  const clamped = Math.max(0, ddPct);
  dom.dd.textContent = `-${clamped.toFixed(1)}% / ${CONFIG.DAILY_DD_LIMIT.toFixed(1)}%`;
  dom.ddMetric.classList.toggle('warning', clamped >= CONFIG.DAILY_DD_WARN);
}

const renderStatus = (online, latency) => {
  if (online) {
    dom.valStatus.textContent = 'BATCH 2 // SL50-TP100';
    dom.statusDot.classList.remove('offline');
  } else {
    dom.valStatus.textContent = 'OFFLINE';
    dom.statusDot.classList.add('offline');
  }
  dom.latency.textContent = online ? `${Math.round(latency)} ms` : '— ms';
};

function renderClock() {
  const now = new Date();
  dom.clock.textContent = now.toTimeString().slice(0, 8) + ' UTC';
}

/* ============================================================
   RENDER — VISUAL MATRIX (CHART)
   ============================================================ */

function initChart() {
  const container = document.getElementById('chart-stub');
  container.innerHTML = ''; // Clear placeholder
  
  const w = container.clientWidth || 600;
  const h = container.clientHeight || 400;

  state.chart = LightweightCharts.createChart(container, {
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#6E6E73',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif',
    },
    grid: {
      vertLines: { color: 'rgba(28, 28, 30, 0.04)' },
      horzLines: { color: 'rgba(28, 28, 30, 0.04)' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: { color: 'rgba(94, 92, 230, 0.3)' },
      horzLine: { color: 'rgba(94, 92, 230, 0.3)' },
    },
    rightPriceScale: {
      borderColor: 'rgba(28, 28, 30, 0.1)',
    },
    timeScale: {
      borderColor: 'rgba(28, 28, 30, 0.1)',
      timeVisible: true,
      secondsVisible: true,
    },
  });

  state.lineSeries = state.chart.addSeries(LightweightCharts.LineSeries, {
    color: '#5E5CE6',
    lineWidth: 2,
    crosshairMarkerRadius: 4,
    lastPriceAnimation: 1,
  });
  
  // Robust resize observer
  const ro = new ResizeObserver(entries => {
    if (entries.length === 0 || entries[0].target !== container) return;
    const newRect = entries[0].contentRect;
    if (newRect.width > 0 && newRect.height > 0) {
      state.chart.applyOptions({ width: newRect.width, height: newRect.height });
    }
  });
  ro.observe(container);
}

function updateChart(price) {
  if (!state.lineSeries) return;
  state.chartTime += 1; // Chart requires integer UNIX timestamps, so we artificially step 1s per tick
  try {
    state.lineSeries.update({ time: state.chartTime, value: price });
  } catch (e) {
    console.error("Chart update error:", e);
  }
}

/* ============================================================
   RENDER — NEURAL FEED  (append-only, capped, auto-scroll)
   ============================================================ */

function makeProbGroup(label, value, isDominant) {
  const wrap = document.createElement('span');
  wrap.className =
    'feed-prob feed-prob--' + label.toLowerCase() + (isDominant ? ' feed-prob--dominant' : '');

  const tag = document.createElement('span');
  tag.textContent = `[${label}:`;
  wrap.appendChild(tag);

  const bar = document.createElement('span');
  bar.className = 'feed-bar';
  const fill = document.createElement('i');
  fill.style.transform = `scaleX(${value})`;
  bar.appendChild(fill);
  wrap.appendChild(bar);

  const val = document.createElement('span');
  val.className = 'feed-prob__val';
  val.textContent = `${value.toFixed(2)}]`;
  wrap.appendChild(val);

  return wrap;
}

function pushFeedLine({ ts, longP, shortP, flatP }) {
  const dominant =
    longP > shortP && longP > flatP ? 'long' : shortP > flatP ? 'short' : 'flat';

  const line = document.createElement('div');
  line.className = 'feed-line';

  const tsEl = document.createElement('span');
  tsEl.className = 'feed-ts';
  tsEl.textContent = `[${ts}]`;
  line.appendChild(tsEl);

  const stateEl = document.createElement('span');
  stateEl.className = 'feed-state';
  stateEl.textContent = '[STATE: EVAL]';
  line.appendChild(stateEl);

  line.appendChild(makeProbGroup('LONG', longP, dominant === 'long'));
  line.appendChild(makeProbGroup('SHORT', shortP, dominant === 'short'));
  line.appendChild(makeProbGroup('FLAT', flatP, dominant === 'flat'));

  dom.feed.appendChild(line);
  dom.feed.scrollTop = dom.feed.scrollHeight;

  // trim from the top — never touches existing nodes, O(1) amortized
  while (dom.feed.childElementCount > CONFIG.MAX_FEED_LINES) {
    dom.feed.removeChild(dom.feed.firstChild);
  }
}

/* ============================================================
   RENDER — EXECUTION LOG  (prepend-only, capped)
   ============================================================ */

function prependTradeRow(trade) {
  const removeEmptyState = dom.logBody.querySelector('.log-empty-row');
  if (removeEmptyState) removeEmptyState.remove();

  const tr = document.createElement('tr');

  const tdTime = document.createElement('td');
  tdTime.className = 'col-time';
  tdTime.textContent = trade.time;
  tr.appendChild(tdTime);

  const tdAction = document.createElement('td');
  const tag = document.createElement('span');
  tag.className = 'action-tag action-tag--' + trade.action.toLowerCase();
  tag.textContent = `[${trade.action}]`;
  tdAction.appendChild(tag);
  tr.appendChild(tdAction);

  const tdEntry = document.createElement('td');
  tdEntry.textContent = fmtPrice(trade.entry);
  tr.appendChild(tdEntry);

  const tdExit = document.createElement('td');
  tdExit.textContent = fmtPrice(trade.exit);
  tr.appendChild(tdExit);

  const tdPnl = document.createElement('td');
  tdPnl.className = trade.pnl >= 0 ? 'pnl--pos' : 'pnl--neg';
  tdPnl.textContent = (trade.pnl >= 0 ? '+' : '') + fmtUSD(trade.pnl).replace('$', '$');
  tr.appendChild(tdPnl);

  const tdDur = document.createElement('td');
  tdDur.textContent = fmtDuration(trade.durationSec);
  tr.appendChild(tdDur);

  dom.logBody.insertBefore(tr, dom.logBody.firstChild);

  state.tradeCount += 1;
  dom.logCount.textContent = `${state.tradeCount} TRADE${state.tradeCount === 1 ? '' : 'S'}`;

  while (dom.logBody.childElementCount > CONFIG.MAX_LOG_ROWS) {
    dom.logBody.removeChild(dom.logBody.lastChild);
  }
}

/* ============================================================
   WEBSOCKET CLIENT  (live backend — ready, currently dormant)
   Expects JSON frames shaped as:
     { type: "killswitch", equity, dailyDD, online, latencyMs }
     { type: "neural",     ts, longP, shortP, flatP }
     { type: "trade",      time, action, entry, exit, pnl, durationSec }
     { type: "price",      value }
   ============================================================ */

class WSClient {
  constructor(url) {
    this.url = url;
    this.backoff = CONFIG.WS_RECONNECT_MIN_MS;
    this.socket = null;
  }

  connect() {
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.backoff = CONFIG.WS_RECONNECT_MIN_MS;
      renderStatus(true, 0);
    };

    this.socket.onmessage = (evt) => {
      let msg;
      try {
        msg = JSON.parse(evt.data);
      } catch {
        return;
      }
      this.route(msg);
    };

    this.socket.onclose = () => {
      renderStatus(false, 0);
      setTimeout(() => this.connect(), this.backoff);
      this.backoff = Math.min(this.backoff * 2, CONFIG.WS_RECONNECT_MAX_MS);
    };

    this.socket.onerror = () => {
      this.socket.close();
    };
  }

  route(msg) {
    switch (msg.type) {
      case 'killswitch':
        renderEquity(msg.equity);
        renderDrawdown(msg.equity);
        renderStatus(msg.online, msg.latencyMs);
        break;
      case 'neural':
        pushFeedLine(msg);
        break;
      case 'trade':
        prependTradeRow(msg);
        break;
      case 'price':
        dom.chartPrice.textContent = fmtPrice(msg.value);
        updateChart(msg.value);
        break;
    }
  }
}

/* ============================================================
   MOCK ENGINE  (for UI testing without a backend)
   ============================================================ */

const MockEngine = (() => {
  let equity = CONFIG.START_EQUITY;
  let price = 18342.5;
  let inPosition = null; // { action, entry, openedAt }
  let latency = CONFIG.MOCK_LATENCY_BASE;
  let timer = null;

  function randomSoftmax() {
    const r1 = Math.random(), r2 = Math.random(), r3 = Math.random();
    const sum = r1 + r2 + r3;
    return [r1 / sum, r2 / sum, r3 / sum];
  }

  function tick() {
    // price random walk
    price += (Math.random() - 0.5) * 6;

    // latency jitter
    latency = CONFIG.MOCK_LATENCY_BASE + Math.random() * 14;

    // neural feed line — biased toward FLAT, matching sparse-trade reality
    let [a, b, c] = randomSoftmax();
    const flatP = Math.max(c, 0.55 + Math.random() * 0.35);
    const remainder = 1 - flatP;
    const longP = remainder * (0.4 + Math.random() * 0.2);
    const shortP = remainder - longP;

    pushFeedLine({
      ts: fmtClockTime(new Date()),
      longP, shortP, flatP,
    });

    dom.chartPrice.textContent = fmtPrice(price);
    updateChart(price);

    // trade lifecycle
    if (!inPosition && Math.random() < CONFIG.MOCK_TRADE_CHANCE) {
      inPosition = {
        action: Math.random() < 0.5 ? 'LONG' : 'SHORT',
        entry: price,
        openedAt: Date.now(),
      };
    } else if (inPosition && Date.now() - inPosition.openedAt > 150 + Math.random() * 300) {
      // HFT Execution: Hold for 150ms to 450ms before violently exiting
      const win = Math.random() < 0.37; // Kessler's target winrate
      const pnl = win ? 2000 * (0.9 + Math.random() * 0.2) : -1000 * (0.9 + Math.random() * 0.2);
      const exit = inPosition.action === 'LONG' ? inPosition.entry + (win ? 100 : -50)
                                                  : inPosition.entry - (win ? 100 : -50);
      equity += pnl;

      prependTradeRow({
        time: fmtClockTime(new Date()).slice(0, 8),
        action: inPosition.action,
        entry: inPosition.entry,
        exit,
        pnl,
        durationSec: (Date.now() - inPosition.openedAt) / 1000,
      });

      renderEquity(equity);
      renderDrawdown(equity);
      
      inPosition = null;
    }

    renderStatus(true, latency);
  }

  return {
    start() {
      renderEquity(equity);
      renderDrawdown(equity);
      timer = setInterval(tick, CONFIG.MOCK_TICK_MS);
    },
    stop() {
      clearInterval(timer);
    },
  };
})();

/* ============================================================
   INIT
   ============================================================ */

function init() {
  setInterval(renderClock, 1000);
  renderClock();
  
  try {
    initChart();
  } catch (e) {
    console.error("Failed to init visual matrix:", e);
    document.getElementById('chart-stub').innerHTML = `<span class="chart-stub__text" style="color:red; font-size:10px;">[ERROR] ${e.toString()}</span>`;
  }

  if (CONFIG.USE_MOCK) {
    MockEngine.start();
  } else {
    new WSClient(CONFIG.WS_URL).connect();
  }
}

document.addEventListener('DOMContentLoaded', init);
