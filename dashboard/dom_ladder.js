// KESSLER 2D LOB (Depth of Market Ladder)

const DOM_ROWS_COUNT = 40;
let currentCenterPrice = 18100.00;

function initDOMLadder() {
    const container = document.getElementById('dom-rows');
    container.innerHTML = '';
    
    // Create rows
    for (let i = 0; i < DOM_ROWS_COUNT; i++) {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.flex = '1';
        row.style.alignItems = 'center';
        row.style.fontFamily = 'var(--font-mono)';
        row.style.fontSize = '11px';
        row.style.borderBottom = '1px solid rgba(255,255,255,0.02)';
        
        // Bids (Left)
        const bidCol = document.createElement('div');
        bidCol.style.flex = '1';
        bidCol.style.height = '100%';
        bidCol.style.display = 'flex';
        bidCol.style.justifyContent = 'flex-end';
        bidCol.style.alignItems = 'center';
        bidCol.style.position = 'relative';
        
        const bidBar = document.createElement('div');
        bidBar.style.position = 'absolute';
        bidBar.style.right = '0';
        bidBar.style.height = '80%';
        bidBar.style.backgroundColor = 'rgba(0, 229, 160, 0.2)'; // #00E5A0
        bidBar.style.transition = 'width 0.1s ease-out';
        
        const bidText = document.createElement('span');
        bidText.style.color = '#00E5A0';
        bidText.style.paddingRight = '8px';
        bidText.style.zIndex = '1';
        
        bidCol.appendChild(bidBar);
        bidCol.appendChild(bidText);
        
        // Price (Center)
        const priceCol = document.createElement('div');
        priceCol.style.width = '80px';
        priceCol.style.textAlign = 'center';
        priceCol.style.fontWeight = '600';
        priceCol.style.color = i === Math.floor(DOM_ROWS_COUNT/2) ? '#FFFFFF' : '#8B93A7';
        priceCol.style.backgroundColor = i === Math.floor(DOM_ROWS_COUNT/2) ? 'rgba(255,255,255,0.1)' : 'transparent';
        
        // Asks (Right)
        const askCol = document.createElement('div');
        askCol.style.flex = '1';
        askCol.style.height = '100%';
        askCol.style.display = 'flex';
        askCol.style.justifyContent = 'flex-start';
        askCol.style.alignItems = 'center';
        askCol.style.position = 'relative';
        
        const askBar = document.createElement('div');
        askBar.style.position = 'absolute';
        askBar.style.left = '0';
        askBar.style.height = '80%';
        askBar.style.backgroundColor = 'rgba(255, 76, 97, 0.2)'; // #FF4C61
        askBar.style.transition = 'width 0.1s ease-out';
        
        const askText = document.createElement('span');
        askText.style.color = '#FF4C61';
        askText.style.paddingLeft = '8px';
        askText.style.zIndex = '1';
        
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
    setInterval(updateDOM, 100);
}

function updateDOM() {
    const container = document.getElementById('dom-rows');
    const rows = container.children;
    
    // Simulate price drift
    if (Math.random() > 0.8) {
        currentCenterPrice += (Math.random() > 0.5 ? 0.25 : -0.25);
    }
    
    const centerIdx = Math.floor(DOM_ROWS_COUNT / 2);
    const startPrice = currentCenterPrice + (centerIdx * 0.25);
    
    for (let i = 0; i < DOM_ROWS_COUNT; i++) {
        const row = rows[i];
        const price = startPrice - (i * 0.25);
        
        row._priceCol.textContent = price.toFixed(2);
        
        // Generate Heatmap Data
        const isAbove = i < centerIdx;
        const isBelow = i > centerIdx;
        
        if (isAbove) {
            // Asks Region
            row._bidBar.style.width = '0%';
            row._bidText.textContent = '';
            
            let askVol = Math.pow(Math.random(), 3) * 100;
            if (i === centerIdx - 10) askVol += 300; // Fake liquidity wall
            
            row._askBar.style.width = Math.min(100, (askVol / 400) * 100) + '%';
            row._askText.textContent = askVol > 5 ? Math.floor(askVol) : '';
        } else if (isBelow) {
            // Bids Region
            row._askBar.style.width = '0%';
            row._askText.textContent = '';
            
            let bidVol = Math.pow(Math.random(), 3) * 100;
            if (i === centerIdx + 12) bidVol += 350; // Fake liquidity wall
            
            row._bidBar.style.width = Math.min(100, (bidVol / 400) * 100) + '%';
            row._bidText.textContent = bidVol > 5 ? Math.floor(bidVol) : '';
        } else {
            // Center Line (Spread)
            row._bidBar.style.width = '0%';
            row._askBar.style.width = '0%';
            row._bidText.textContent = '';
            row._askText.textContent = '';
        }
    }
}

document.addEventListener('DOMContentLoaded', initDOMLadder);
