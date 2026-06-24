// KESSLER 2D LOB (Depth of Market Ladder) - Premium 'c2' Edition

const DOM_ROWS_COUNT = 45;
let currentCenterPrice = 18336.25;
let tickCount = 0;

function initDOMLadder() {
    const container = document.getElementById('dom-rows');
    container.innerHTML = '';
    
    // Create rows
    for (let i = 0; i < DOM_ROWS_COUNT; i++) {
        const row = document.createElement('div');
        row.className = 'dom-row';
        row.style.display = 'flex';
        row.style.flex = '1';
        row.style.alignItems = 'stretch'; // Fill vertical space
        row.style.fontFamily = 'var(--font-mono)';
        row.style.fontSize = '12px';
        row.style.borderBottom = '1px solid rgba(255,255,255,0.03)';
        row.style.cursor = 'crosshair';
        row.style.transition = 'background 0.1s ease';
        
        row.addEventListener('mouseenter', () => row.style.background = 'rgba(255,255,255,0.05)');
        row.addEventListener('mouseleave', () => row.style.background = 'transparent');
        
        // Bids (Left)
        const bidCol = document.createElement('div');
        bidCol.style.flex = '1';
        bidCol.style.display = 'flex';
        bidCol.style.justifyContent = 'flex-end';
        bidCol.style.alignItems = 'center';
        bidCol.style.position = 'relative';
        
        const bidBar = document.createElement('div');
        bidBar.style.position = 'absolute';
        bidBar.style.right = '0';
        bidBar.style.height = '100%';
        bidBar.style.background = 'linear-gradient(90deg, rgba(0,229,160,0.02) 0%, rgba(0,229,160,0.25) 100%)';
        bidBar.style.borderRight = '2px solid rgba(0,229,160,0.8)';
        bidBar.style.transition = 'width 0.15s cubic-bezier(0.4, 0, 0.2, 1)';
        
        const bidText = document.createElement('span');
        bidText.style.color = 'rgba(0,229,160,0.9)';
        bidText.style.paddingRight = '12px';
        bidText.style.zIndex = '1';
        bidText.style.fontWeight = '500';
        bidText.style.textShadow = '0 0 10px rgba(0,229,160,0.3)';
        
        bidCol.appendChild(bidBar);
        bidCol.appendChild(bidText);
        
        // Price (Center)
        const priceCol = document.createElement('div');
        priceCol.style.width = '100px';
        priceCol.style.display = 'flex';
        priceCol.style.justifyContent = 'center';
        priceCol.style.alignItems = 'center';
        priceCol.style.fontWeight = '600';
        priceCol.style.letterSpacing = '0.5px';
        priceCol.style.color = '#8B93A7';
        priceCol.style.borderLeft = '1px solid rgba(255,255,255,0.05)';
        priceCol.style.borderRight = '1px solid rgba(255,255,255,0.05)';
        priceCol.style.background = 'rgba(0,0,0,0.2)';
        
        // Asks (Right)
        const askCol = document.createElement('div');
        askCol.style.flex = '1';
        askCol.style.display = 'flex';
        askCol.style.justifyContent = 'flex-start';
        askCol.style.alignItems = 'center';
        askCol.style.position = 'relative';
        
        const askBar = document.createElement('div');
        askBar.style.position = 'absolute';
        askBar.style.left = '0';
        askBar.style.height = '100%';
        askBar.style.background = 'linear-gradient(270deg, rgba(255,76,97,0.02) 0%, rgba(255,76,97,0.25) 100%)';
        askBar.style.borderLeft = '2px solid rgba(255,76,97,0.8)';
        askBar.style.transition = 'width 0.15s cubic-bezier(0.4, 0, 0.2, 1)';
        
        const askText = document.createElement('span');
        askText.style.color = 'rgba(255,76,97,0.9)';
        askText.style.paddingLeft = '12px';
        askText.style.zIndex = '1';
        askText.style.fontWeight = '500';
        askText.style.textShadow = '0 0 10px rgba(255,76,97,0.3)';
        
        askCol.appendChild(askBar);
        askCol.appendChild(askText);
        
        // Attach elements to row
        row.appendChild(bidCol);
        row.appendChild(priceCol);
        row.appendChild(askCol);
        
        container.appendChild(row);
        
        // Store references
        row.dataset.index = i;
        row._bidBar = bidBar;
        row._bidText = bidText;
        row._priceCol = priceCol;
        row._askBar = askBar;
        row._askText = askText;
    }
    
    // Start live updates
    setInterval(updateDOM, 80); // ultra-fast 12.5 Hz refresh for silky smooth DOM
}

function updateDOM() {
    const container = document.getElementById('dom-rows');
    const rows = container.children;
    tickCount++;
    
    // Micro-volatility price drift
    if (Math.random() > 0.85) {
        currentCenterPrice += (Math.random() > 0.5 ? 0.25 : -0.25);
    }
    
    const centerIdx = Math.floor(DOM_ROWS_COUNT / 2);
    const startPrice = currentCenterPrice + (centerIdx * 0.25);
    
    // Dynamic liquidity nodes to simulate institution resting orders
    const fakeBidNode = centerIdx + 8 + Math.floor(Math.sin(tickCount * 0.1) * 3);
    const fakeAskNode = centerIdx - 10 + Math.floor(Math.cos(tickCount * 0.1) * 3);
    
    for (let i = 0; i < DOM_ROWS_COUNT; i++) {
        const row = rows[i];
        const price = startPrice - (i * 0.25);
        
        // Formatting the price string to look strictly institutional (e.g., highlighting the last 2 digits)
        const priceStr = price.toFixed(2);
        row._priceCol.textContent = priceStr;
        
        const isSpread = i === centerIdx;
        const isAsk = i < centerIdx;
        const isBid = i > centerIdx;
        
        // Center Price Styling
        if (isSpread) {
            row._priceCol.style.color = '#FFFFFF';
            row._priceCol.style.background = 'rgba(255,255,255,0.1)';
            row._priceCol.style.textShadow = '0 0 8px rgba(255,255,255,0.4)';
        } else {
            row._priceCol.style.color = '#8B93A7';
            row._priceCol.style.background = 'rgba(0,0,0,0.2)';
            row._priceCol.style.textShadow = 'none';
        }
        
        // Heatmap Processing
        if (isAsk) {
            row._bidBar.style.width = '0%';
            row._bidBar.style.borderRight = 'none';
            row._bidText.textContent = '';
            
            let askVol = (Math.pow(Math.random(), 3) * 60) + 5; 
            if (i === fakeAskNode) askVol += 280 + (Math.random() * 50); // Whale Order
            
            const w = Math.min(100, (askVol / 350) * 100);
            row._askBar.style.width = w + '%';
            row._askBar.style.borderLeft = w > 0 ? '2px solid rgba(255,76,97,0.8)' : 'none';
            row._askText.textContent = askVol > 10 ? Math.floor(askVol) : '';
            
        } else if (isBid) {
            row._askBar.style.width = '0%';
            row._askBar.style.borderLeft = 'none';
            row._askText.textContent = '';
            
            let bidVol = (Math.pow(Math.random(), 3) * 60) + 5;
            if (i === fakeBidNode) bidVol += 310 + (Math.random() * 50); // Whale Order
            
            const w = Math.min(100, (bidVol / 350) * 100);
            row._bidBar.style.width = w + '%';
            row._bidBar.style.borderRight = w > 0 ? '2px solid rgba(0,229,160,0.8)' : 'none';
            row._bidText.textContent = bidVol > 10 ? Math.floor(bidVol) : '';
            
        } else {
            // Spread Clearance
            row._bidBar.style.width = '0%';
            row._askBar.style.width = '0%';
            row._bidBar.style.borderRight = 'none';
            row._askBar.style.borderLeft = 'none';
            row._bidText.textContent = '';
            row._askText.textContent = '';
        }
    }
}

document.addEventListener('DOMContentLoaded', initDOMLadder);
