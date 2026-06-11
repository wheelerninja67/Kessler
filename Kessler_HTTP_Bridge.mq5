//+------------------------------------------------------------------+
//|                                     Kessler_HTTP_Bridge.mq5      |
//|                 Zero-DLL HTTP Bridge for Wine/Linux Environments |
//+------------------------------------------------------------------+
#property copyright "Kessler Engine"
#property version   "1.00"
#property strict

// IMPORTANT: You MUST allow WebRequests to http://127.0.0.1:5555
// Go to Tools -> Options -> Expert Advisors -> Allow WebRequest -> Add URL

input string ServerURL = "http://127.0.0.1:5555";
input int    PollIntervalMs = 1000; // Poll every 1 second

int OnInit() {
    Print("[*] Kessler HTTP Bridge Initialized.");
    EventSetMillisecondTimer(PollIntervalMs);
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    EventKillTimer();
    Print("[*] Kessler HTTP Bridge Terminated.");
}

void OnTimer() {
    // 1. Poll Python for signals
    string cookie=NULL, headers;
    char post[], result[];
    
    int res = WebRequest("GET", ServerURL + "/get_signal", cookie, NULL, 500, post, 0, result, headers);
    
    if (res == 200) {
        string response = CharArrayToString(result);
        if (response != "NONE") {
            Print("[!!!] SIGNAL RECEIVED FROM KESSLER PYTHON ENGINE: ", response);
            ExecuteKesslerSignal(response);
        }
    } else if (res == -1) {
        // Suppress timeout errors
    }
    
    // 2. Push Market Data to Python every 5 seconds
    static datetime last_push = 0;
    if (TimeCurrent() - last_push >= 5) {
        SendMarketData();
        last_push = TimeCurrent();
    }
}

void SendMarketData() {
    double o[], h[], l[], c[];
    // Get 500 candles of M5 data
    if (CopyOpen(Symbol(), PERIOD_M5, 0, 500, o) < 500) return;
    CopyHigh(Symbol(), PERIOD_M5, 0, 500, h);
    CopyLow(Symbol(), PERIOD_M5, 0, 500, l);
    CopyClose(Symbol(), PERIOD_M5, 0, 500, c);
    
    string payload = "";
    for(int i=0; i<500; i++) {
        payload += DoubleToString(o[i], 2) + "," + DoubleToString(h[i], 2) + "," + DoubleToString(l[i], 2) + "," + DoubleToString(c[i], 2) + "|";
    }
    
    string cookie=NULL, headers;
    char post[], result[];
    StringToCharArray(payload, post);
    WebRequest("POST", ServerURL + "/market_data", cookie, NULL, 500, post, ArraySize(post), result, headers);
}

void ExecuteKesslerSignal(string json_payload) {
    string arr[];
    StringSplit(json_payload, ',', arr);
    if(ArraySize(arr) < 4) return;
    
    string direction = arr[0];
    double raw_volume = StringToDouble(arr[1]);
    double sl_dist = StringToDouble(arr[2]);
    double tp_dist = StringToDouble(arr[3]);
    
    MqlTradeRequest request;
    MqlTradeResult trade_result;
    ZeroMemory(request);
    ZeroMemory(trade_result);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = Symbol();
    request.type_time = ORDER_TIME_GTC;
    
    // Safely determine allowed filling mode
    int fill_mode = (int)SymbolInfoInteger(Symbol(), SYMBOL_FILLING_MODE);
    if ((fill_mode & SYMBOL_FILLING_FOK) != 0) {
        request.type_filling = ORDER_FILLING_FOK;
    } else if ((fill_mode & SYMBOL_FILLING_IOC) != 0) {
        request.type_filling = ORDER_FILLING_IOC;
    } else {
        request.type_filling = ORDER_FILLING_RETURN;
    }
    
    request.magic = 777777;
    request.comment = "Kessler V1.3";
    
    // 1. Bypass Volume Rejections (Force alignment to broker limits)
    double vol_step = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_STEP);
    double vol_min = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MIN);
    double vol_max = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MAX);
    double volume = MathRound(raw_volume / vol_step) * vol_step;
    if (volume < vol_min) volume = vol_min;
    if (volume > vol_max) volume = vol_max;
    request.volume = volume;
    
    double entry_price = 0;
    double calculated_sl = 0;
    double calculated_tp = 0;
    
    if (direction == "LONG") {
        request.type = ORDER_TYPE_BUY;
        entry_price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
        calculated_sl = entry_price - sl_dist;
        calculated_tp = entry_price + tp_dist;
    } else if (direction == "SHORT") {
        request.type = ORDER_TYPE_SELL;
        entry_price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
        calculated_sl = entry_price + sl_dist;
        calculated_tp = entry_price - tp_dist;
    } else {
        return;
    }
    
    request.price = entry_price;
    request.deviation = 50; // High slippage tolerance for volatile indices
    
    // 2. Bypass Invalid Stop Rejections (Two-Step Execution: Send naked order first)
    request.sl = 0.0;
    request.tp = 0.0;
    
    Print("[*] STEP 1: Sending NAKED Market Order: ", direction, " ", volume, " lots");
    
    if(!OrderSend(request, trade_result)) {
        Print("[!] ENTRY SERVER REJECTION: ", trade_result.retcode);
        SendFeedback("ENTRY REJECTION: " + IntegerToString(trade_result.retcode));
        return;
    } 
    
    Print("[+] Entry SUCCESS. Preparing Step 2 (Modify SL/TP)...");
    Sleep(500); // 500ms delay to let the position register on the server
    
    // 3. Step 2: Attach SL and TP to the live position
    if(PositionSelect(Symbol())) {
        MqlTradeRequest mod_request;
        MqlTradeResult mod_result;
        ZeroMemory(mod_request);
        ZeroMemory(mod_result);
        
        mod_request.action = TRADE_ACTION_SLTP;
        mod_request.symbol = Symbol();
        mod_request.position = PositionGetInteger(POSITION_TICKET);
        mod_request.sl = calculated_sl;
        mod_request.tp = calculated_tp;
        
        if(!OrderSend(mod_request, mod_result)) {
            Print("[!] SL/TP MODIFY REJECTION: ", mod_result.retcode);
            SendFeedback("SLTP REJECTION: " + IntegerToString(mod_result.retcode));
            
            // ==========================================
            // CRITICAL FAIL-SAFE: KILL NAKED POSITION
            // ==========================================
            Print("[!!!] FAIL-SAFE TRIGGERED. Closing naked position to protect capital.");
            MqlTradeRequest kill_req;
            MqlTradeResult kill_res;
            ZeroMemory(kill_req);
            ZeroMemory(kill_res);
            
            kill_req.action = TRADE_ACTION_DEAL;
            kill_req.symbol = Symbol();
            kill_req.type_time = ORDER_TIME_GTC;
            kill_req.type_filling = request.type_filling;
            kill_req.position = mod_request.position;
            kill_req.volume = PositionGetDouble(POSITION_VOLUME);
            
            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) {
                kill_req.type = ORDER_TYPE_SELL;
                kill_req.price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
            } else {
                kill_req.type = ORDER_TYPE_BUY;
                kill_req.price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
            }
            
            OrderSend(kill_req, kill_res);
            SendFeedback("POSITION KILLED: SL FAILED TO ATTACH");
            // ==========================================
            
        } else {
            Print("[+] SL/TP Attached Successfully. Trade is fully secured.");
            SendFeedback("SUCCESS: " + IntegerToString((int)trade_result.deal));
        }
    } else {
        SendFeedback("ERROR: Could not find position to attach SL/TP.");
    }
}

void SendFeedback(string message) {
    string cookie=NULL, headers;
    char post[], result[];
    StringToCharArray(message, post);
    WebRequest("POST", ServerURL + "/feedback", cookie, NULL, 500, post, ArraySize(post), result, headers);
}
//+------------------------------------------------------------------+
