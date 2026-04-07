import datetime
import pandas as pd
import numpy as np
import math
import os
import json

# ==========================================
# STRATEGY CONSTANTS (EXACTLY FROM BACKTEST)
# ==========================================

RISK_PER_TRADE_PCT = 0.025
MOMENTUM_MAX_OPEN_POS = 10
PYRAMID_MAX_ADDS = 6
PYRAMID_TRIGGER_PCT = 2.5
PARTIAL_BOOK_QTY_PCT = 0.33

# TIME STOP SETTINGS
TIME_STOP_THRESHOLD_PCT = 3.0
TIME_STOP_BASE_DAYS = 25
TIME_STOP_VOLATILE_DAYS = 12

# BLOCK LIST FILE
BLOCKED_STOCKS_FILE = "Blocked_Stocks.json"

class LiveStrategyEngine:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.kite = bot_instance.kite
        self.blocked_stocks = self.load_blocked_stocks()
        
    def load_blocked_stocks(self):
        if os.path.exists(BLOCKED_STOCKS_FILE):
            try:
                with open(BLOCKED_STOCKS_FILE, "r") as f:
                    data = json.load(f)
                    # Convert date strings back to objects
                    parsed = {}
                    for sym, date_str in data.items():
                        parsed[sym] = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    return parsed
            except Exception as e:
                self.bot.log_event(f"⚠️ Error loading blocked stocks: {e}", "error")
                return {}
        return {}

    def save_blocked_stocks(self):
        data = {}
        for sym, date_obj in self.blocked_stocks.items():
            data[sym] = date_obj.strftime("%Y-%m-%d")
        
        with open(BLOCKED_STOCKS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def log(self, msg, level="info"):
        self.bot.log_event(msg, level)

    # ==========================================
    # 1. LIVE DATA FETCHING (EXACT LOGIC)
    # ==========================================

    def get_tech_data(self, symbol):
        token = self.bot.get_instrument_token(symbol)
        if not token:
            print(f"❌ Token missing for {symbol}")
            return None

        to_date = datetime.datetime.now().date()
        from_date = to_date - datetime.timedelta(days=400)

        try:
            # Fetch last 400 days to ensure enough data for 200 DMA + lookback
            candles = self.kite.historical_data(token, from_date, to_date, "day")
            df = pd.DataFrame(candles)
        except Exception as e:
            print(f"⚠️ API Error fetching {symbol}: {e}")
            return None

        if len(df) < 201: return None

        curr = df.iloc[-1]
        closes = df['close'].values
        current_close = closes[-1]

        # Indicators - EXACT FORMULAS
        dma_50 = df['close'].rolling(50).mean().iloc[-1]
        dma_20 = df['close'].rolling(20).mean().iloc[-1]
        dma_200 = df['close'].rolling(200).mean().iloc[-1]
        avg_vol_20 = df['volume'].rolling(20).mean().iloc[-1]

        # ATR Calculation
        calc_df = df.tail(60).copy()
        calc_df['tr0'] = abs(calc_df['high'] - calc_df['low'])
        calc_df['tr1'] = abs(calc_df['high'] - calc_df['close'].shift())
        calc_df['tr2'] = abs(calc_df['low'] - calc_df['close'].shift())
        calc_df['tr'] = calc_df[['tr0', 'tr1', 'tr2']].max(axis=1)
        calc_df['atr'] = calc_df['tr'].rolling(14).mean()
        atr_val = calc_df['atr'].iloc[-1]
        atr_ma_20 = calc_df['atr'].rolling(20).mean().iloc[-1]

        # RSI (EMA based)
        delta = calc_df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        calc_df['rsi'] = 100 - (100 / (1 + rs))
        rsi_val = calc_df['rsi'].iloc[-1]

        prev_close = df.iloc[-2]['close']

        # Max Return Ranges
        def get_max_ret_range(min_days, max_days):
            max_r = -999.0
            if len(closes) < (max_days + 1): return -999.0
            for d in range(min_days, max_days + 1):
                prev_price = closes[-(d + 1)]
                if prev_price > 0:
                    r = ((current_close - prev_price) / prev_price) * 100
                    if r > max_r: max_r = r
            return max_r

        ret_55_65 = get_max_ret_range(55, 65)
        ret_17_23 = get_max_ret_range(17, 23)
        ret_4_6 = get_max_ret_range(4, 6)
        ret_15_25 = get_max_ret_range(15, 25)
        
        # Returns
        ret_1d = ((current_close - prev_close) / prev_close) * 100
        ret_1m = ((current_close - df.iloc[-20]['close']) / df.iloc[-20]['close'] * 100) if len(df) > 20 else 0
        ret_3m = ((current_close - df.iloc[-63]['close']) / df.iloc[-63]['close'] * 100) if len(df) > 63 else 0
        ret_6m = ((current_close - df.iloc[-126]['close']) / df.iloc[-126]['close'] * 100) if len(df) > 126 else 0
        ret_1w = ((current_close - df.iloc[-5]['close']) / df.iloc[-5]['close'] * 100) if len(df) > 5 else 0

        return {
            'close': current_close, 'prev_close': prev_close,
            'volume': curr['volume'], '20_avg_vol': avg_vol_20,
            '20_dma': dma_20, '50_dma': dma_50, '200_dma': dma_200,
            'atr_val': atr_val, 'atr_ma_20': atr_ma_20,
            'rsi': rsi_val,
            'ret_1d': ret_1d, 'ret_1w': ret_1w, 'ret_1m': ret_1m,
            'ret_3m': ret_3m, 'ret_6m': ret_6m,
            'max_ret_55_65': ret_55_65, 'max_ret_17_23': ret_17_23,
            'max_ret_4_6': ret_4_6, 'max_ret_15_25': ret_15_25
        }

    def get_sensex_regime(self):
        """
        Market Regime Logic:
        Crash  > Trend > Sideways
        If ANY index crashes → Crash
        Else if ANY index trends → Trend
        Else → Sideways
        """

        sensex = self.get_tech_data("BSE-SENSEX")
        nifty = self.get_tech_data("NSE-NIFTY 50")

        if not sensex and not nifty:
            return "Sideways"

        def classify(index_data):
            if not index_data:
                return "Sideways"

            close = index_data['close']
            dma_50 = index_data['50_dma']
            dma_200 = index_data['200_dma']

            if close < dma_200 * 0.99 and dma_50 < dma_200:
                return "Crash"
            elif close > dma_50 and close > dma_200:
                return "Trend"
            else:
                return "Sideways"

        sensex_regime = classify(sensex)
        nifty_regime = classify(nifty)

        # PRIORITY LOGIC
        if "Crash" in (sensex_regime, nifty_regime):
            return "Crash"
        elif "Trend" in (sensex_regime, nifty_regime):
            return "Trend"
        else:
            return "Sideways"


    # ==========================================
    # 2. ORDER MANAGEMENT (ADAPTED FOR LIVE)
    # ==========================================

    def manage_orders(self, symbol, price, action="BUY", exit_reason=None, sl_price_input=0, strategy="Momentum",
                      quantity_override=0, risk_per_trade=RISK_PER_TRADE_PCT, signal_mult=1.0, is_high_vol=False):
        
        # Current Date
        today = datetime.date.today()
        
        # Load Config for Capital
        available_cash = self.bot.get_strategy_cash_wrapper()


        if action == "BUY":
            # --- SIGNAL STRENGTH SIZING ---
            adjusted_risk_pct = risk_per_trade * signal_mult
            risk_amt = available_cash * adjusted_risk_pct

            stop_distance = price - sl_price_input
            if stop_distance <= 0: stop_distance = price * 0.05

            qty = int(risk_amt / stop_distance)
            if qty < 1: qty = 1

            # Cap max capital exposure
            max_cap_alloc = 0.30 if signal_mult <= 1.0 else 0.45
            
            # Check against available cash and allocation limits
            # Note: available_cash is already the strategy's portion
            if (qty * price) > (available_cash * max_cap_alloc):
                qty = int((available_cash * max_cap_alloc) / price)
            
            if (qty * price) > available_cash:
                qty = int(available_cash / price)

            if qty < 1: 
                self.log(f"⚠️ {symbol}: Qty < 1 after sizing. Skipping.", "warning")
                return False

            # EXECUTE ORDER
            tag = "MOMENTUM_BUY"
            success = self.bot.execute_broker_order(symbol, self.bot.kite.TRANSACTION_TYPE_BUY, qty, tag)
            
            if success:
                # Time Stop Assignment
                max_hold_days = TIME_STOP_VOLATILE_DAYS if is_high_vol else TIME_STOP_BASE_DAYS
                
                # Update Position in TradeBook
                self.bot.tb.positions[symbol] = {
                    'entry_price': price,
                    'entry_time': today.strftime("%Y-%m-%d"), # Persist as string or adjust bot to handle date obj
                    'max_hold_days': max_hold_days,
                    'qty': qty,
                    'sl_price': sl_price_input,
                    'strategy': strategy,
                    'pyramid_count': 0,
                    'partial_booked': False,
                    'initial_entry_price': price,
                    'initial_qty': qty
                }
                self.bot.tb.save() # Persist immediately
                self.bot.tb.log_history(symbol, self.bot.tb.positions[symbol], price, "ENTRY") # Log Entry
                return True
            return False

        elif action == "ADD": # Reflexive Pyramiding
            if symbol not in self.bot.tb.positions: return False
            pos = self.bot.tb.positions[symbol]
            
            # Helper to parse entry time if string
            if isinstance(pos['entry_time'], str):
                pos['entry_time'] = datetime.datetime.strptime(pos['entry_time'], "%Y-%m-%d").date()

            p_count = pos.get('pyramid_count', 0)
            
            if p_count == 0: scale_factor = 0.60
            elif p_count == 1: scale_factor = 0.30
            else: scale_factor = 0.15

            add_qty = int(pos.get('initial_qty', pos['qty']) * scale_factor)
            if add_qty < 1: add_qty = 1

            val = add_qty * price
            if val > available_cash: 
                self.log(f"⚠️ {symbol}: Insufficient cash to pyramid.", "warning")
                return False

            # EXECUTE ORDER
            tag = "MOMENTUM_ADD"
            success = self.bot.execute_broker_order(symbol, self.bot.kite.TRANSACTION_TYPE_BUY, add_qty, tag)

            if success:
                old_qty = pos['qty']
                old_price = pos['entry_price']
                new_avg = ((old_qty * old_price) + (add_qty * price)) / (old_qty + add_qty)

                pos['qty'] += add_qty
                pos['entry_price'] = new_avg
                pos['pyramid_count'] = p_count + 1
                pos['sl_price'] = max(pos['sl_price'], new_avg * 0.96) # Tighten SL

                self.bot.tb.save()
                self.log(f"➕ REFLEXIVE PYRAMID {symbol} | Step: {p_count + 1} | Add Qty: {add_qty}", "trade")
                return True
            return False

        elif action == "SELL":
            if symbol not in self.bot.tb.positions: return False
            pos = self.bot.tb.positions[symbol]

            if exit_reason == "PARTIAL":
                qty_to_sell = quantity_override
                if qty_to_sell >= pos['qty']: return False

                # EXECUTE ORDER
                tag = "MOMENTUM_PARTIAL"
                success = self.bot.execute_broker_order(symbol, self.bot.kite.TRANSACTION_TYPE_SELL, qty_to_sell, tag)

                if success:
                    pos['qty'] -= qty_to_sell
                    pos['partial_booked'] = True
                    # Raise SL to 1% above entry
                    pos['sl_price'] = max(pos['sl_price'], pos['entry_price'] * 1.01)
                    
                    self.bot.tb.save()
                    self.bot.tb.log_history(symbol, pos, price, "PARTIAL_PROFIT")
                    return True
                return False

            else: # FULL EXIT
                qty = pos['qty']
                
                # EXECUTE ORDER
                tag = f"EXIT_{exit_reason}"
                success = self.bot.execute_broker_order(symbol, self.bot.kite.TRANSACTION_TYPE_SELL, qty, tag)

                if success:
                    block_days = 0
                    if exit_reason == "SL": block_days = 10
                    elif exit_reason == "TIME_STOP": block_days = 5

                    self.bot.tb.log_history(symbol, pos, price, exit_reason)
                    del self.bot.tb.positions[symbol] # Remove from active positions
                    self.bot.tb.save()

                    if block_days > 0:
                        expiry_date = today + datetime.timedelta(days=block_days)
                        self.blocked_stocks[symbol] = expiry_date
                        self.save_blocked_stocks()

                    return True
                return False
        return False

    # ==========================================
    # 3. MAIN STRATEGY LOOP
    # ==========================================

    def run_strategy(self):
        self.log("🔄 Starting Strategy Execution...", "info")
        
        # Remove expired blocks
        today = datetime.date.today()
        expired_blocks = [s for s, d in self.blocked_stocks.items() if today >= d]
        for s in expired_blocks:
            del self.blocked_stocks[s]
        if expired_blocks:
            self.save_blocked_stocks()

        regime = self.get_sensex_regime()
        self.log(f"📊 Market Regime: {regime}", "info")
        
        sensex_data = self.get_tech_data("BSE-SENSEX")
        sensex_ret_1m = sensex_data['ret_1m'] if sensex_data else 0

        is_trend = (regime == "Trend")
        is_crash = (regime == "Crash")

        if is_trend:
            allow_momentum = True
            current_risk_pct = RISK_PER_TRADE_PCT
            current_max_pos = MOMENTUM_MAX_OPEN_POS
            allow_pyramid = True
        elif is_crash:
            allow_momentum = True
            current_risk_pct = 0.0075
            current_max_pos = 3
            allow_pyramid = False
        else:
            allow_momentum = False
            current_risk_pct = 0
            current_max_pos = 0
            allow_pyramid = False

        # --- MANAGE EXISTING POSITIONS ---
        # Iterate over a copy of keys because we might delete positions
        for sym in list(self.bot.tb.positions.keys()):
            pos = self.bot.tb.positions[sym]
            
            # Handle string dates from JSON
            if isinstance(pos.get('entry_time'), str):
                pos['entry_time'] = datetime.datetime.strptime(pos['entry_time'], "%Y-%m-%d").date()

            ind = self.get_tech_data(sym)
            if not ind: continue

            curr_price = ind['close']
            entry_price = pos['entry_price']
            pnl_pct = ((curr_price - entry_price) / entry_price) * 100

            # TIME STOP LOGIC (FIXED)
            days_held = (today - pos['entry_time']).days
            max_hold = pos.get('max_hold_days', TIME_STOP_BASE_DAYS)

            if days_held > max_hold:
                # Exit only if trend weak
                if curr_price < ind['20_dma']:
                    self.manage_orders(sym, curr_price, "SELL", exit_reason="TIME_STOP")
                    continue

            # 2. HARD STOP LOSS
            if curr_price <= pos['sl_price']:
                self.manage_orders(sym, curr_price, "SELL", exit_reason="SL")
                continue

            # 3. TREND EXIT (RSI + 20 DMA)
            if curr_price < ind['20_dma'] and ind['rsi'] < 40:
                self.manage_orders(sym, curr_price, "SELL", exit_reason="TREND")
                continue

            # 4. PARTIAL PROFIT
            is_euphoric = (ind['rsi'] > 85 and curr_price > (1.35 * ind['20_dma']) and ind['volume'] < ind['20_avg_vol'])
            is_crash_target = is_crash and (pnl_pct > 6.0)
            
            if (is_euphoric or is_crash_target) and not pos.get('partial_booked', False):
                book_qty = int(pos['qty'] * PARTIAL_BOOK_QTY_PCT)
                if book_qty > 0:
                    self.manage_orders(sym, curr_price, "SELL", exit_reason="PARTIAL", quantity_override=book_qty)
                    # pos sl update is handled inside manage_orders
            
            # 5. REFLEXIVE PYRAMIDING
            pct_move_from_start = ((curr_price - pos.get('initial_entry_price', entry_price)) / pos.get('initial_entry_price', entry_price)) * 100
            
            reflexive_vol = ind['volume'] > (1.5 * ind['20_avg_vol'])
            reflexive_price = ind['ret_1d'] > 2.0
            reflexive_signal = reflexive_vol or reflexive_price

            p_count = pos.get('pyramid_count', 0)
            
            trigger_level = PYRAMID_TRIGGER_PCT * (p_count + 1)
            
            if pct_move_from_start > trigger_level and p_count < PYRAMID_MAX_ADDS:
                if allow_momentum and allow_pyramid and reflexive_signal:
                     self.manage_orders(sym, curr_price, "ADD")

            # 6. TRAILING STOP UPGRADE
            if pnl_pct > 10:
                be_level = entry_price * 1.02
                if p_count > 0:
                    trend_sl = ind['20_dma']
                else:
                    trend_sl = ind['50_dma']
                
                new_sl = max(pos['sl_price'], be_level, trend_sl)
                if new_sl < curr_price:
                    pos['sl_price'] = new_sl
                    self.bot.tb.save() # Persist SL update

        # --- ENTRY LOGIC ---
        if not allow_momentum: 
            self.log("🚫 Momentum entries not allowed in current regime.", "warning")
            return

        mom_count = len(self.bot.tb.positions)
        if mom_count >= current_max_pos: 
            self.log("🚫 Max positions reached. Skipping scan.", "warning")
            return

        # Access universe via bot instance
        if not hasattr(self.bot, 'stock_master_data'):
             self.log("⚠️ stock_master_data not found in bot instance", "error")
             return

        candidates = []
        
        for stock in self.bot.stock_master_data:
            sym = stock['symbol']
            mcap = stock['mcap']
            
            if sym in self.bot.tb.positions: continue
            if sym in self.blocked_stocks: continue # Block check
            
            ind = self.get_tech_data(sym)
            if not ind: continue

            # Basic Filters
            if mcap < 10000: continue
            if (ind['close'] * ind['20_avg_vol']) < 550000000: continue

            valid_candidate = False
            signal_score = 1.0
            
            is_high_vol = ind['atr_val'] > (1.1 * ind['atr_ma_20'])

            if is_crash:
                c_trend = (ind['close'] > ind['200_dma']) and (ind['close'] > ind['50_dma'])
                c_rsi = ind['rsi'] > 60
                c_vol = ind['volume'] > (1.3 * ind['20_avg_vol'])
                c_rs = (ind['ret_1m'] - sensex_ret_1m) > 10.0
                
                if c_trend and c_rsi and c_vol and c_rs:
                    valid_candidate = True
                    signal_score = 1.0
            
            elif is_trend:
                # Standard Logic
                if ind['ret_3m'] < 15 or ind['ret_6m'] < 25: continue
                if not ((ind['close'] > ind['prev_close']) and (ind['rsi'] > 40)): continue

                c1 = ind['max_ret_55_65'] > 12.0
                c2 = ind['max_ret_17_23'] > 8.0
                c3 = ind['max_ret_4_6'] > 2.0
                c11 = ind['close'] <= (1.15 * ind['20_dma'])
                
                vol_expansion = ind['volume'] > (1.54 * ind['20_avg_vol'])
                c6 = (vol_expansion and ind['ret_1d'] > 0) or (vol_expansion and c11)
                
                c7 = ind['close'] > ind['200_dma']
                c9 = ind['rsi'] > 55
                c10 = ind['close'] < (2.2 * ind['200_dma'])
                c_atr_rise = ind['atr_val'] > ind['atr_ma_20']

                if c1 and c2 and c3 and c6 and c7 and c9 and c10 and c11 and c_atr_rise:
                    valid_candidate = True
                    
                    # Score Calculation
                    s_vol = 1 if ind['volume'] > (2.0 * ind['20_avg_vol']) else 0
                    s_mom = 1 if ind['ret_1m'] > 15.0 else 0
                    s_rsi = 1 if (65 < ind['rsi'] < 75) else 0
                    s_trend = 1 if (ind['close'] > ind['50_dma']) else 0
                    
                    strength_sum = s_vol + s_mom + s_rsi + s_trend
                    
                    if strength_sum >= 3: signal_score = 2.5
                    elif strength_sum == 2: signal_score = 1.5
                    else: signal_score = 1.0

            if valid_candidate:
                vol_shock_pct = ((ind['volume'] / ind['20_avg_vol']) - 1) * 100
                trend_score = ((ind['close'] - ind['200_dma']) / ind['200_dma']) * 100
                
                rank_score = (0.35 * ind['ret_1m']) + (0.25 * ind['ret_1w']) + \
                             (0.20 * vol_shock_pct) + (0.10 * ind['rsi']) + (0.10 * trend_score)
                
                rank_score *= signal_score
                
                candidates.append({
                    'symbol': sym,
                    'score': rank_score,
                    'price': ind['close'],
                    'atr': ind['atr_val'],
                    'signal_mult': signal_score,
                    'is_high_vol': is_high_vol
                })
        
        # Sort and Pick
        candidates.sort(key=lambda x: x['score'], reverse=True)
        slots = current_max_pos - mom_count
        
        self.log(f"🔎 Found {len(candidates)} candidates. Slots available: {slots}", "info")

        for pick in candidates[:slots]:
            sl_price = min(pick['price'] - (3.5 * pick['atr']), pick['price'] * 0.92)
            
            self.manage_orders(pick['symbol'], pick['price'], "BUY", sl_price_input=sl_price,
                               risk_per_trade=current_risk_pct,
                               signal_mult=pick['signal_mult'],
                               is_high_vol=pick['is_high_vol'])
