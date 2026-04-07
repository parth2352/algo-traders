import time
import datetime
import pandas as pd
import numpy as np
import json
import os
import sys
import csv
import asyncio
import uvicorn
from collections import deque
from fastapi import FastAPI, BackgroundTasks, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from kiteconnect import KiteConnect
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4
import secrets
from strategy_engine import LiveStrategyEngine

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================

ACCESS_TOKEN_DIR = "AccessToken"

# 🔹 ZERODHA CREDENTIALS
API_KEY = "8x9vlt8d40tff3ik"
API_SECRET = "23cc37e3q68kema4glznq9kd7cijwvmn"

# 🔹 GLOBAL SETTINGS
TRADEBOOK_JSON = "Live_TradeBook.json"
TRADEBOOK_EXCEL = "Live_TradeBook.xlsx"
TRADE_HISTORY_CSV = "TradeHistory.csv"
EQUITY_CURVE_JSON = "Equity_Curve.json" 
STRATEGY_CONFIG_JSON = "Strategy_Config.json" # New file for persistent capital

DEFAULT_FIXED_CAPITAL = 1000000.0

RISK_PER_TRADE_PCT = 0.025
MOMENTUM_MAX_OPEN_POS = 10
PYRAMID_MAX_ADDS = 6
PYRAMID_TRIGGER_PCT = 2.5
PARTIAL_BOOK_QTY_PCT = 0.33

# 🔹 TIME STOP SETTINGS
TIME_STOP_THRESHOLD_PCT = 3.0
TIME_STOP_BASE_DAYS = 25
TIME_STOP_VOLATILE_DAYS = 12

# 🔹 UNIVERSE (EXACT COPY)
STOCK_MASTER_DATA = [
{"symbol": "NSE-RVNL", "mcap": 65959.61},
{"symbol": "NSE-NAUKRI", "mcap": 66761.38},
{"symbol": "NSE-GICRE", "mcap": 67202.29},
{"symbol": "NSE-LLOYDSME", "mcap": 67218.79},
{"symbol": "NSE-ALKEM", "mcap": 67428.68},
{"symbol": "NSE-SCHAEFFLER", "mcap": 68104.64},
{"symbol": "NSE-SAIL", "mcap": 68446.93},
{"symbol": "NSE-POLICYBZR", "mcap": 68552.61},
{"symbol": "NSE-UNOMINDA", "mcap": 68625.94},
{"symbol": "NSE-IOB", "mcap": 70190.27},
{"symbol": "NSE-FSL", "mcap": 15070.3},
{"symbol": "NSE-ECLERX", "mcap": 15116.6},
{"symbol": "NSE-THELEELA", "mcap": 15146.66},
{"symbol": "NSE-KAJARIACER", "mcap": 15243.95},
{"symbol": "NSE-CGCL", "mcap": 15363.67},
{"symbol": "NSE-ARE&M", "mcap": 15464.73},
{"symbol": "NSE-TRITURBINE", "mcap": 15551.28},
{"symbol": "NSE-KEC", "mcap": 15580.69},
{"symbol": "NSE-VTL", "mcap": 15692.57},
{"symbol": "NSE-DEVYANI", "mcap": 15711.72},
{"symbol": "NSE-JINDALSTEL", "mcap": 126919.36},
{"symbol": "NSE-ABB", "mcap": 128691.96},
{"symbol": "NSE-POLYCAB", "mcap": 129630.58},
{"symbol": "NSE-LTM", "mcap": 132295.32},
{"symbol": "NSE-TECHM", "mcap": 133034.49},
{"symbol": "NSE-INDIANB", "mcap": 133416.78},
{"symbol": "NSE-MUTHOOTFIN", "mcap": 134632.45},
{"symbol": "NSE-IRFC", "mcap": 135324.38},
{"symbol": "NSE-CUMMINSIND", "mcap": 135780.88},
{"symbol": "NSE-PFC", "mcap": 136558.21},
{"symbol": "NSE-ACC", "mcap": 29903.24},
{"symbol": "NSE-GLAND", "mcap": 30021.91},
{"symbol": "NSE-MEDANTA", "mcap": 30609.85},
{"symbol": "NSE-CHOLAFIN", "mcap": 30684.72},
{"symbol": "NSE-KPRMILL", "mcap": 30688.06},
{"symbol": "NSE-KARURVYSYA", "mcap": 31527.48},
{"symbol": "NSE-NAVINFLUOR", "mcap": 32067.2},
{"symbol": "NSE-FORCEMOT", "mcap": 32072.34},
{"symbol": "NSE-DELHIVERY", "mcap": 32440.99},
{"symbol": "NSE-JBCHEPHARM", "mcap": 32970.73},
{"symbol": "NSE-ULTRACEMCO", "mcap": 373564.79},
{"symbol": "NSE-HCLTECH", "mcap": 376955.22},
{"symbol": "NSE-TITAN", "mcap": 384189.46},
{"symbol": "NSE-ITC", "mcap": 392916.63},
{"symbol": "NSE-KOTAKBANK", "mcap": 412971.36},
{"symbol": "NSE-SUNPHARMA", "mcap": 416764.48},
{"symbol": "NSE-M&M", "mcap": 422476.49},
{"symbol": "NSE-AXISBANK", "mcap": 429969.7},
{"symbol": "NSE-MARUTI", "mcap": 467107.9},
{"symbol": "NSE-INFY", "mcap": 527241.4},
{"symbol": "NSE-TIINDIA", "mcap": 53283.71},
{"symbol": "NSE-JSWINFRA", "mcap": 53508.04},
{"symbol": "NSE-UPL", "mcap": 53807.05},
{"symbol": "NSE-HINDCOPPER", "mcap": 54762.57},
{"symbol": "NSE-VMM", "mcap": 55038.63},
{"symbol": "NSE-PATANJALI", "mcap": 55266.24},
{"symbol": "NSE-OBEROIRLTY", "mcap": 55369.35},
{"symbol": "NSE-ATGL", "mcap": 56310.28},
{"symbol": "NSE-MAHABANK", "mcap": 57502.06},
{"symbol": "NSE-SUZLON", "mcap": 58049.78},
{"symbol": "NSE-JMFINANCIL", "mcap": 12216.59},
{"symbol": "NSE-SCI", "mcap": 12272.43},
{"symbol": "NSE-THANGAMAYL", "mcap": 12305.99},
{"symbol": "NSE-ENGINERSIN", "mcap": 12463.29},
{"symbol": "NSE-KIRLOSBROS", "mcap": 12568.84},
{"symbol": "NSE-DEEPAKFERT", "mcap": 12573.29},
{"symbol": "NSE-INDIACEM", "mcap": 12581.83},
{"symbol": "NSE-PARADEEP", "mcap": 12611.32},
{"symbol": "NSE-USHAMART", "mcap": 12750.4},
{"symbol": "NSE-CONCORDBIO", "mcap": 12769.45},
{"symbol": "NSE-ZYDUSLIFE", "mcap": 92744.59},
{"symbol": "NSE-MANKIND", "mcap": 92782.07},
{"symbol": "NSE-LENSKART", "mcap": 93315},
{"symbol": "NSE-HINDPETRO", "mcap": 93358.21},
{"symbol": "NSE-SHREECEM", "mcap": 94080.55},
{"symbol": "NSE-ICICIGI", "mcap": 94741.32},
{"symbol": "NSE-ICICIPRULI", "mcap": 94836.34},
{"symbol": "NSE-INDHOTEL", "mcap": 94950.05},
{"symbol": "NSE-GVT&D", "mcap": 98584.37},
{"symbol": "NSE-LODHA", "mcap": 98715.28},
{"symbol": "NSE-SCHNEIDER", "mcap": 21673.22},
{"symbol": "NSE-WELCORP", "mcap": 21769.32},
{"symbol": "NSE-PINELABS", "mcap": 21841.37},
{"symbol": "NSE-REDINGTON", "mcap": 21924.86},
{"symbol": "NSE-NETWEB", "mcap": 21987.08},
{"symbol": "NSE-ASTRAZEN", "mcap": 22122.5},
{"symbol": "NSE-WOCKPHARMA", "mcap": 22129.81},
{"symbol": "NSE-ASAHIINDIA", "mcap": 22961.29},
{"symbol": "NSE-TENNIND", "mcap": 23461.52},
{"symbol": "NSE-IKS", "mcap": 23617.42},
{"symbol": "NSE-HYUNDAI", "mcap": 175947.65},
{"symbol": "NSE-TVSMOTOR", "mcap": 183844.46},
{"symbol": "NSE-TMCV", "mcap": 186068.2},
{"symbol": "NSE-INDIGO", "mcap": 186625.73},
{"symbol": "NSE-GRASIM", "mcap": 190532.65},
{"symbol": "NSE-SHRIRAMFIN", "mcap": 203092.15},
{"symbol": "NSE-SBILIFE", "mcap": 204334.58},
{"symbol": "NSE-HINDALCO", "mcap": 207801.04},
{"symbol": "NSE-WIPRO", "mcap": 210766.8},
{"symbol": "NSE-EICHERMOT", "mcap": 219739.39},
{"symbol": "NSE-NH", "mcap": 37416.42},
{"symbol": "NSE-ENDURANCE", "mcap": 37440.23},
{"symbol": "NSE-CONCOR", "mcap": 37749.59},
{"symbol": "NSE-FLUOROCHEM", "mcap": 38264.05},
{"symbol": "NSE-IPCALAB", "mcap": 38788.84},
{"symbol": "NSE-COCHINSHIP", "mcap": 39243.76},
{"symbol": "NSE-ESCORTS", "mcap": 39365.31},
{"symbol": "NSE-ANTHEM", "mcap": 39390.18},
{"symbol": "NSE-COFORGE", "mcap": 39817.09},
{"symbol": "NSE-BLUESTARCO", "mcap": 39913.94},
{"symbol": "NSE-PAYTM", "mcap": 70272.36},
{"symbol": "NSE-AUROPHARMA", "mcap": 70881.03},
{"symbol": "NSE-LTF", "mcap": 71089.37},
{"symbol": "NSE-FORTIS", "mcap": 71166.13},
{"symbol": "NSE-AUBANK", "mcap": 71668.6},
{"symbol": "NSE-NMDC", "mcap": 71864.32},
{"symbol": "NSE-MEESHO", "mcap": 72205.58},
{"symbol": "NSE-BAJAJHFL", "mcap": 72524.64},
{"symbol": "NSE-SBICARD", "mcap": 73691.5},
{"symbol": "NSE-FEDERALBNK", "mcap": 73866.73},
{"symbol": "NSE-SAGILITY", "mcap": 18514.65},
{"symbol": "NSE-JYOTICNC", "mcap": 18658.93},
{"symbol": "NSE-ANANTRAJ", "mcap": 19066.28},
{"symbol": "NSE-GESHIP", "mcap": 19115.1},
{"symbol": "NSE-AFFLE", "mcap": 19385.11},
{"symbol": "NSE-ATUL", "mcap": 19649.43},
{"symbol": "NSE-CPPLUS", "mcap": 19896.1},
{"symbol": "NSE-AADHARHFC", "mcap": 19945.63},
{"symbol": "NSE-KIRLOSENG", "mcap": 20250.12},
{"symbol": "NSE-CREDITACC", "mcap": 20260.52},
{"symbol": "NSE-BLS", "mcap": 11475.22},
{"symbol": "NSE-WHIRLPOOL", "mcap": 11695.68},
{"symbol": "NSE-MTARTECH", "mcap": 11709.56},
{"symbol": "NSE-JINDALSAW", "mcap": 11854.56},
{"symbol": "NSE-PRIVISCL", "mcap": 11873.5},
{"symbol": "NSE-GRAVITA", "mcap": 11905.3},
{"symbol": "NSE-LUMAXTECH", "mcap": 11978.04},
{"symbol": "NSE-WELSPUNLIV", "mcap": 12021.06},
{"symbol": "NSE-MGL", "mcap": 12048.91},
{"symbol": "NSE-PCBL", "mcap": 12173.73},
{"symbol": "NSE-ASIANPAINT", "mcap": 227924.58},
{"symbol": "NSE-ETERNAL", "mcap": 237688.14},
{"symbol": "NSE-NESTLEIND", "mcap": 249080.36},
{"symbol": "NSE-ADANIENT", "mcap": 249510.79},
{"symbol": "NSE-DMART", "mcap": 250376.06},
{"symbol": "NSE-HINDZINC", "mcap": 255124.76},
{"symbol": "NSE-HAL", "mcap": 261705.03},
{"symbol": "NSE-IOC", "mcap": 264730.86},
{"symbol": "NSE-TATASTEEL", "mcap": 265062.73},
{"symbol": "NSE-COALINDIA", "mcap": 265397.9},
{"symbol": "NSE-KALYANKJIL", "mcap": 42349.5},
{"symbol": "NSE-GLAXO", "mcap": 43564.46},
{"symbol": "NSE-MOTILALOFS", "mcap": 43628.38},
{"symbol": "NSE-JKCEMENT", "mcap": 43702.92},
{"symbol": "NSE-MPHASIS", "mcap": 43786.88},
{"symbol": "NSE-360ONE", "mcap": 44754.51},
{"symbol": "NSE-ASTRAL", "mcap": 44808.16},
{"symbol": "NSE-APARINDS", "mcap": 44910.18},
{"symbol": "NSE-TATACOMM", "mcap": 45528.75},
{"symbol": "NSE-IRCTC", "mcap": 45564},
{"symbol": "NSE-CIPLA", "mcap": 108904.99},
{"symbol": "NSE-BSE", "mcap": 110259.93},
{"symbol": "NSE-GAIL", "mcap": 111467.66},
{"symbol": "NSE-APOLLOHOSP", "mcap": 112461.17},
{"symbol": "NSE-TATACONSUM", "mcap": 112908.56},
{"symbol": "NSE-POWERINDIA", "mcap": 113935.88},
{"symbol": "NSE-CGPOWER", "mcap": 114212.37},
{"symbol": "NSE-HEROMOTOCO", "mcap": 114251.26},
{"symbol": "NSE-IDEA", "mcap": 114735.27},
{"symbol": "NSE-HDFCAMC", "mcap": 115597.21},
{"symbol": "NSE-ABSLAMC", "mcap": 25805.88},
{"symbol": "NSE-KAYNES", "mcap": 25851.91},
{"symbol": "NSE-ITI", "mcap": 26034.19},
{"symbol": "NSE-TIMKEN", "mcap": 26122.71},
{"symbol": "NSE-CDSL", "mcap": 26588.98},
{"symbol": "NSE-RAMCOCEM", "mcap": 26696.31},
{"symbol": "NSE-PTCIL", "mcap": 26890.64},
{"symbol": "NSE-ATHERENERG", "mcap": 27180.23},
{"symbol": "NSE-STARHEALTH", "mcap": 27389.96},
{"symbol": "NSE-EMCURE", "mcap": 27592.28},
{"symbol": "NSE-CANHLIFE", "mcap": 13598.3},
{"symbol": "NSE-TECHNOE", "mcap": 13644.27},
{"symbol": "NSE-TEGA", "mcap": 13655.96},
{"symbol": "NSE-SHRIRAMFIN", "mcap": 13729.89},
{"symbol": "NSE-NIVABUPA", "mcap": 13870.61},
{"symbol": "NSE-SIGNATURE", "mcap": 13907.75},
{"symbol": "NSE-LTFOODS", "mcap": 13969.99},
{"symbol": "NSE-FINCABLES", "mcap": 13974.07},
{"symbol": "NSE-BEML", "mcap": 14000.88},
{"symbol": "NSE-GRAPHITE", "mcap": 14029.92},
{"symbol": "NSE-LICI", "mcap": 537245.3},
{"symbol": "NSE-HINDUNILVR", "mcap": 549357.93},
{"symbol": "NSE-LT", "mcap": 588527.88},
{"symbol": "NSE-BAJFINANCE", "mcap": 619696.97},
{"symbol": "NSE-TCS", "mcap": 954234.4},
{"symbol": "NSE-ICICIBANK", "mcap": 986915.07},
{"symbol": "NSE-BHARTIARTL", "mcap": 1071596.65},
{"symbol": "NSE-SBIN", "mcap": 1109243.32},
{"symbol": "NSE-HDFCBANK", "mcap": 1366198.01},
{"symbol": "NSE-RELIANCE", "mcap": 1886290.84},
{"symbol": "NSE-LAURUSLABS", "mcap": 58077.77},
{"symbol": "NSE-HDBFS", "mcap": 58557.19},
{"symbol": "NSE-PHOENIXLTD", "mcap": 59313.54},
{"symbol": "NSE-NAM-INDIA", "mcap": 59341.65},
{"symbol": "NSE-MRF", "mcap": 59793.75},
{"symbol": "NSE-PRESTIGE", "mcap": 60000.72},
{"symbol": "NSE-GLENMARK", "mcap": 60297.85},
{"symbol": "NSE-OFSS", "mcap": 60328.64},
{"symbol": "NSE-SUNDARMFIN", "mcap": 61212.67},
{"symbol": "NSE-COLPAL", "mcap": 61319.16},
{"symbol": "NSE-ANURAS", "mcap": 14109.22},
{"symbol": "NSE-GRANULES", "mcap": 14129.39},
{"symbol": "NSE-DOMS", "mcap": 14152.52},
{"symbol": "NSE-CEATLTD", "mcap": 14284.55},
{"symbol": "NSE-CHENNPETRO", "mcap": 14324.53},
{"symbol": "NSE-GABRIEL", "mcap": 14347.16},
{"symbol": "NSE-ABREL", "mcap": 14410.98},
{"symbol": "NSE-JKTYRE", "mcap": 14446.19},
{"symbol": "NSE-SANSERA", "mcap": 14574.17},
{"symbol": "NSE-SOBHA", "mcap": 14918.2},
{"symbol": "NSE-TRENT", "mcap": 138622.34},
{"symbol": "NSE-MOTHERSON", "mcap": 140732.94},
{"symbol": "NSE-TMPV", "mcap": 140906.18},
{"symbol": "NSE-TATACAP", "mcap": 141608.83},
{"symbol": "NSE-CANBK", "mcap": 142744.84},
{"symbol": "NSE-BRITANNIA", "mcap": 144581.19},
{"symbol": "NSE-TORNTPHARM", "mcap": 146658.56},
{"symbol": "NSE-CHOLAFIN", "mcap": 147438.13},
{"symbol": "NSE-PNB", "mcap": 148764.66},
{"symbol": "NSE-DLF", "mcap": 149471.7},
{"symbol": "NSE-GODFRYPHLP", "mcap": 32996.38},
{"symbol": "NSE-PREMIERENE", "mcap": 33113.89},
{"symbol": "NSE-SONACOMS", "mcap": 33230.99},
{"symbol": "NSE-TATAINVEST", "mcap": 33327.12},
{"symbol": "NSE-ASTERDM", "mcap": 33916.2},
{"symbol": "NSE-JUBLFOOD", "mcap": 34305.35},
{"symbol": "NSE-IREDA", "mcap": 34342.85},
{"symbol": "NSE-MRPL", "mcap": 34464.85},
{"symbol": "NSE-RADICO", "mcap": 35475.08},
{"symbol": "NSE-PAGEIND", "mcap": 35815.09},
{"symbol": "NSE-UNITDSPR", "mcap": 100432.61},
{"symbol": "NSE-FIRSTCRY", "mcap": 100932.13},
{"symbol": "NSE-MARICO", "mcap": 102377.47},
{"symbol": "NSE-ENRIN", "mcap": 104375.36},
{"symbol": "NSE-LUPIN", "mcap": 105206.78},
{"symbol": "NSE-GRINFRA", "mcap": 106254.98},
{"symbol": "NSE-MAXHEALTH", "mcap": 106256.87},
{"symbol": "NSE-DRREDDY", "mcap": 107360.13},
{"symbol": "NSE-BOSCHLTD", "mcap": 107430.58},
{"symbol": "NSE-LGEINDIA", "mcap": 107856.93},
{"symbol": "NSE-TATATECH", "mcap": 23757.66},
{"symbol": "NSE-IGL", "mcap": 23920.43},
{"symbol": "NSE-MANAPPURAM", "mcap": 23975.26},
{"symbol": "NSE-AEGISVOPAK", "mcap": 24164.6},
{"symbol": "NSE-HSCL", "mcap": 24461.6},
{"symbol": "NSE-AWL", "mcap": 24576.92},
{"symbol": "NSE-PWL", "mcap": 24756.36},
{"symbol": "NSE-NBCC", "mcap": 25020.9},
{"symbol": "NSE-IRB", "mcap": 25188.67},
{"symbol": "NSE-ANANDRATHI", "mcap": 25536.32},
{"symbol": "NSE-AAVAS", "mcap": 10180.91},
{"symbol": "NSE-SBFC", "mcap": 10299.61},
{"symbol": "NSE-VIJAYA", "mcap": 10335.98},
{"symbol": "NSE-ACE", "mcap": 10535.29},
{"symbol": "NSE-AFCONS", "mcap": 10744.83},
{"symbol": "NSE-EDELWEISS", "mcap": 10829.61},
{"symbol": "NSE-BSOFT", "mcap": 10903.54},
{"symbol": "NSE-AZAD", "mcap": 11064.14},
{"symbol": "NSE-HEG", "mcap": 11148.31},
{"symbol": "NSE-TI", "mcap": 11219.08},
{"symbol": "NSE-INDUSINDBK", "mcap": 74540.98},
{"symbol": "NSE-PERSISTENT", "mcap": 74663.08},
{"symbol": "NSE-NHPC", "mcap": 75669.25},
{"symbol": "NSE-SRF", "mcap": 75949.97},
{"symbol": "NSE-NTPCGREEN", "mcap": 75954.94},
{"symbol": "NSE-NYKAA", "mcap": 76008.47},
{"symbol": "NSE-WAAREEENER", "mcap": 77930.55},
{"symbol": "NSE-OIL", "mcap": 78711.55},
{"symbol": "NSE-TORNTPOWER", "mcap": 78931.45},
{"symbol": "NSE-BANKINDIA", "mcap": 80149.72},
{"symbol": "NSE-SYRMA", "mcap": 15855.49},
{"symbol": "NSE-INOXWIND", "mcap": 15922.26},
{"symbol": "NSE-AARTIIND", "mcap": 16213.41},
{"symbol": "NSE-CHOICEIN", "mcap": 16415.29},
{"symbol": "NSE-NEULANDLAB", "mcap": 16454.33},
{"symbol": "NSE-BELRISE", "mcap": 16705.7},
{"symbol": "NSE-NAVA", "mcap": 16855.56},
{"symbol": "NSE-ELGIEQUIP", "mcap": 16946.71},
{"symbol": "NSE-BRIGADE", "mcap": 16976.01},
{"symbol": "NSE-SYNGENE", "mcap": 17012.1},
{"symbol": "NSE-INDUSTOWER", "mcap": 120023.21},
{"symbol": "NSE-BAJAJHLDNG", "mcap": 120237.72},
{"symbol": "NSE-TATAPOWER", "mcap": 120640.04},
{"symbol": "NSE-ADANIENSOL", "mcap": 121515.75},
{"symbol": "NSE-SIEMENS", "mcap": 121743.36},
{"symbol": "NSE-SOLARINDS", "mcap": 122197.77},
{"symbol": "NSE-AMBUJACEM", "mcap": 123690.05},
{"symbol": "NSE-ASHOKLEY", "mcap": 123997.07},
{"symbol": "NSE-GODREJCP", "mcap": 124580.03},
{"symbol": "NSE-IDBI", "mcap": 124738.62},
{"symbol": "NSE-GRSE", "mcap": 27883.1},
{"symbol": "NSE-AMBER", "mcap": 28061.84},
{"symbol": "NSE-TATAELXSI", "mcap": 28114.08},
{"symbol": "NSE-EXIDEIND", "mcap": 28415.5},
{"symbol": "NSE-SJVN", "mcap": 28699.29},
{"symbol": "NSE-APOLLOTYRE", "mcap": 28836.76},
{"symbol": "NSE-HEXT", "mcap": 28931.61},
{"symbol": "NSE-BANDHANBNK", "mcap": 29316.46},
{"symbol": "NSE-LICHSGFIN", "mcap": 29579.64},
{"symbol": "NSE-KIMS", "mcap": 29812.35},
{"symbol": "NSE-ADANIPOWER", "mcap": 270197.86},
{"symbol": "NSE-POWERGRID", "mcap": 277762.53},
{"symbol": "NSE-BAJAJ-AUTO", "mcap": 278729.22},
{"symbol": "NSE-VEDL", "mcap": 280922.28},
{"symbol": "NSE-JSWSTEEL", "mcap": 309276.56},
{"symbol": "NSE-BAJAJFINSV", "mcap": 319053.64},
{"symbol": "NSE-BEL", "mcap": 325065.86},
{"symbol": "NSE-ADANIPORTS", "mcap": 350432.18},
{"symbol": "NSE-ONGC", "mcap": 351870.41},
{"symbol": "NSE-NTPC", "mcap": 370315.68},
{"symbol": "NSE-BALKRISIND", "mcap": 46084.88},
{"symbol": "NSE-BDL", "mcap": 46377.49},
{"symbol": "NSE-PIIND", "mcap": 47295.09},
{"symbol": "NSE-FACT", "mcap": 48106.57},
{"symbol": "NSE-PETRONET", "mcap": 48510},
{"symbol": "NSE-KEI", "mcap": 48568.93},
{"symbol": "NSE-SUPREMEIND", "mcap": 50495.72},
{"symbol": "NSE-VOLTAS", "mcap": 51661.03},
{"symbol": "NSE-M&MFIN", "mcap": 52026.62},
{"symbol": "NSE-GODREJPROP", "mcap": 52138.82},
{"symbol": "NSE-INDIAMART", "mcap": 12810.58},
{"symbol": "NSE-ZENSARTECH", "mcap": 12844.13},
{"symbol": "NSE-RUBICON", "mcap": 12856.29},
{"symbol": "NSE-MINDACORP", "mcap": 13282.06},
{"symbol": "NSE-TBOTEK", "mcap": 13310.69},
{"symbol": "NSE-J&KBANK", "mcap": 13367.25},
{"symbol": "NSE-AKZOINDIA", "mcap": 13367.45},
{"symbol": "NSE-BLUEDART", "mcap": 13484.57},
{"symbol": "NSE-EMMVEE", "mcap": 13513.88},
{"symbol": "NSE-CCL", "mcap": 13552.42},
{"symbol": "NSE-BHARTIHEXA", "mcap": 80345},
{"symbol": "NSE-SWIGGY", "mcap": 83292.46},
{"symbol": "NSE-JSWENERGY", "mcap": 85711.93},
{"symbol": "NSE-HAVELLS", "mcap": 87634.05},
{"symbol": "NSE-MAZDOCK", "mcap": 89748.02},
{"symbol": "NSE-ABCAPITAL", "mcap": 90214.63},
{"symbol": "NSE-BHARATFORG", "mcap": 91372.3},
{"symbol": "NSE-DABUR", "mcap": 91965.84},
{"symbol": "NSE-RECLTD", "mcap": 92110.18},
{"symbol": "NSE-BHEL", "mcap": 92257.27},
{"symbol": "NSE-KIOCL", "mcap": 20502.48},
{"symbol": "NSE-PPLPHARMA", "mcap": 20753.55},
{"symbol": "NSE-CESC", "mcap": 20963.9},
{"symbol": "NSE-CUB", "mcap": 21031.95},
{"symbol": "NSE-IIFL", "mcap": 21102.65},
{"symbol": "NSE-KPITTECH", "mcap": 21139.23},
{"symbol": "NSE-SAILIFE", "mcap": 21139.75},
{"symbol": "NSE-KPIL", "mcap": 21177.5},
{"symbol": "NSE-PNBHOUSING", "mcap": 21485.44},
{"symbol": "NSE-DEEPAKNTR", "mcap": 21559.65},
{"symbol": "NSE-PIDILITIND", "mcap": 151842.93},
{"symbol": "NSE-VBL", "mcap": 152667.74},
{"symbol": "NSE-ICICIAMC", "mcap": 153818.19},
{"symbol": "NSE-HDFCLIFE", "mcap": 154334.26},
{"symbol": "NSE-UNIONBANK", "mcap": 154404.94},
{"symbol": "NSE-ADANIGREEN", "mcap": 156045.23},
{"symbol": "NSE-JIOFIN", "mcap": 162259.24},
{"symbol": "NSE-BANKBARODA", "mcap": 166492.01},
{"symbol": "NSE-BPCL", "mcap": 167206},
{"symbol": "NSE-DIVISLAB", "mcap": 170125.54},
{"symbol": "NSE-NLCINDIA", "mcap": 36059.49},
{"symbol": "NSE-CENTRALBK", "mcap": 36268.96},
{"symbol": "NSE-ITCHOTELS", "mcap": 36671.24},
{"symbol": "NSE-POONAWALLA", "mcap": 36965.64},
{"symbol": "NSE-UCOBANK", "mcap": 37142.17},
{"symbol": "NSE-THERMAX", "mcap": 37150.55},
{"symbol": "NSE-LTTS", "mcap": 37230.08},
{"symbol": "NSE-DALBHARAT", "mcap": 37381.89},
{"symbol": "NSE-HUDCO", "mcap": 37385.48},
{"symbol": "NSE-AJANTPHARM", "mcap": 37404.48},
{"symbol": "NSE-APLAPOLLO", "mcap": 62040.55},
{"symbol": "NSE-MCX", "mcap": 62302.16},
{"symbol": "NSE-MFSL", "mcap": 62583.11},
{"symbol": "NSE-BIOCON", "mcap": 63182.98},
{"symbol": "NSE-IDFCFIRSTB", "mcap": 63186.86},
{"symbol": "NSE-JSL", "mcap": 64003.81},
{"symbol": "NSE-DIXON", "mcap": 64012.24},
{"symbol": "NSE-YESBANK", "mcap": 65018.16},
{"symbol": "NSE-NATIONALUM", "mcap": 65126.96},
{"symbol": "NSE-COROMANDEL", "mcap": 65493.25},
{"symbol": "NSE-AVANTIFEED", "mcap": 17477.59},
{"symbol": "NSE-RRKABEL", "mcap": 17673.17},
{"symbol": "NSE-ACUTAAS", "mcap": 17674.34},
{"symbol": "NSE-NATCOPHARM", "mcap": 17705.01},
{"symbol": "NSE-PGEL", "mcap": 17916.67},
{"symbol": "NSE-CRAFTSMAN", "mcap": 17953.71},
{"symbol": "NSE-DATAPATTNS", "mcap": 17971.97},
{"symbol": "NSE-TATACHEM", "mcap": 18276.48},
{"symbol": "NSE-CHAMBLFERT", "mcap": 18480.09},
{"symbol": "NSE-CASTROLIND", "mcap": 18487.69},
{"symbol": "BSE-SENSEX", "mcap": 0},
{"symbol": "NSE-NIFTY 50", "mcap": 0}
]

ALL_WATCHLIST_SYMBOLS = list(set([s['symbol'] for s in STOCK_MASTER_DATA]))

# ==========================================
# 2. GLOBAL STATE & LOGGING
# ==========================================


# 🔹 SECURITY STORE
ACCESS_SESSIONS = {}
# access_session_id -> {
#   "created_at": datetime,
#   "ip": str,
#   "user_agent": str,
#   "kite": KiteConnect | None,
#   "bot": LiveBot | None
# }

# Dummy Auth Check (Replace with DB or Config Later)
def verify_user(username, password):
    # CHANGE THESE CREDENTIALS
    return username == "sudhir" and password == "Ranjana@352"

# 🔐 SECURITY CONSTANTS
SESSION_TTL_SECONDS = 6 * 60 * 60  # 6 hours

PUBLIC_ROUTES = {
    "/auth/login",
    "/auth/login-page",
    "/kite/callback",
    "/static/login.html",
    "/favicon.ico"
}

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Allow Public Routes & Login Assets
        if path in PUBLIC_ROUTES or path.startswith("/auth") or path == "/favicon.ico":
            return await call_next(request)

        # 2. Check Session Existence
        session_id = request.cookies.get("access_session")
        if not session_id:
            log_event(f"❌ Middleware Blocked: No 'access_session' cookie in {request.url.path}", "error")
            if path.startswith("/api") or "json" in request.headers.get("accept", ""):
                 return JSONResponse(status_code=401, content={"error": "Missing cookie"})
            return RedirectResponse("/auth/login-page")
        
        if session_id not in ACCESS_SESSIONS:
            log_event(f"❌ Middleware Blocked: Session ID not in memory in {request.url.path} (App likely restarted)", "error")
            if path.startswith("/api") or "json" in request.headers.get("accept", ""):
                 return JSONResponse(status_code=401, content={"error": "Session wiped from memory"})
            return RedirectResponse("/auth/login-page")

        session = ACCESS_SESSIONS[session_id]


        # 3. Security: Session Expiry (TTL)
        age = (datetime.datetime.utcnow() - session["created_at"]).total_seconds()
        if age > SESSION_TTL_SECONDS:
            ACCESS_SESSIONS.pop(session_id, None)
            return RedirectResponse("/auth/login-page")

        # 4. Bind Session Context
        request.state.session = session

        return await call_next(request)

app = FastAPI()
app.add_middleware(SecurityMiddleware)

from fastapi.staticfiles import StaticFiles

# ensure static folder exists
if not os.path.exists("static"):
    os.makedirs("static")

# [FIREWALL] Serve dashboard ONLY after auth
@app.get("/dashboard")
def dashboard(request: Request):
    return FileResponse("static/index.html")
@app.get("/terminal")
def terminal(request: Request):
    return FileResponse("static/terminal_pro.html")

@app.post("/reconcile")
def manual_reconcile(request: Request):
    bot = request.state.session.get("bot")
    if not bot:
        return JSONResponse(status_code=400, content={"error": "Bot instance not found in session"})
    
    try:
        log_event("🔄 Manual reconciliation triggered via API...", "info")
        bot.reconcile_with_broker()
        return {"status": "success", "message": "Reconciliation completed"}
    except Exception as e:
        log_event(f"❌ Manual reconciliation failed: {e}", "error")
        return JSONResponse(status_code=500, content={"error": str(e)})

# [FIREWALL] Static files are now protected by Middleware
# app.mount("/static", StaticFiles(directory="static"), name="static") # REMOVED FOR SECURITY

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard", status_code=302)
# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Log Buffer for UI
log_buffer = deque(maxlen=200)
system_status = {"connected": False, "regime": "Unknown", "last_scan": None}
latest_sensex = {"price": 0.0, "change_pct": 0.0, "regime": "Waiting"}
latest_nifty = {"price": 0.0, "change_pct": 0.0}

# Global Instances (Legacy / Background Task Support)
# We will use these as fallbacks or for background tasks, but primary access is via SESSION
_legacy_bot = None 

# Helper to define active bot for background tasks (Finds first active session with a bot)
def get_current_active_bot():
    for session_id, data in ACCESS_SESSIONS.items():
        if data.get("bot"):
            return data["bot"]
    return None
kill_switch_active = False # Emergency Stop
scan_results = [] # Store latest candidates

def log_event(msg, level="info"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] {msg}"
    print(log_entry)
    log_buffer.append({"time": timestamp, "msg": msg, "type": level})


def today_access_token_exists():
    today = datetime.date.today().strftime("%Y-%m-%d")
    token_file = os.path.join(ACCESS_TOKEN_DIR, f"{today}.json")
    return os.path.exists(token_file)


# ==========================================
# NEW: PERSISTENT CONFIG MANAGEMENT
# ==========================================
def load_strategy_config():
    if os.path.exists(STRATEGY_CONFIG_JSON):
        try:
            with open(STRATEGY_CONFIG_JSON, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mode": "TOTAL_EQUITY", "fixed_capital": DEFAULT_FIXED_CAPITAL}

def save_strategy_config(config_dict):
    with open(STRATEGY_CONFIG_JSON, "w") as f:
        json.dump(config_dict, f, indent=4)

# ==========================================
# 3. CORE CLASSES (UNCHANGED TRADING LOGIC)
# ==========================================

class TradeBookManager:
    """Handles the Backend Sheet (JSON & Excel)"""

    def __init__(self):
        self.positions = {}
        self.load()

    def load(self):
        if os.path.exists(TRADEBOOK_JSON):
            try:
                with open(TRADEBOOK_JSON, "r") as f:
                    data = json.load(f)
                    # Convert date strings back to objects
                    for sym, pos in data.items():
                        if 'entry_time' in pos:
                            pos['entry_time'] = datetime.datetime.strptime(pos['entry_time'], "%Y-%m-%d").date()
                    self.positions = data
                log_event(f"📂 Loaded {len(self.positions)} active positions from TradeBook.")
            except Exception as e:
                log_event(f"⚠️ Error loading TradeBook: {e}", "error")
                self.positions = {}
        else:
            self.positions = {}

    def save(self):
        # Convert date objects to string for JSON serialization
        serializable_pos = {}
        for sym, pos in self.positions.items():
            entry_cpy = pos.copy()
            if isinstance(entry_cpy.get('entry_time'), datetime.date):
                entry_cpy['entry_time'] = entry_cpy['entry_time'].strftime("%Y-%m-%d")
            serializable_pos[sym] = entry_cpy

        # 1. Save JSON (Backend memory)
        with open(TRADEBOOK_JSON, "w") as f:
            json.dump(serializable_pos, f, indent=4)

        # 2. Save Excel (User View)
        if self.positions:
            df = pd.DataFrame.from_dict(serializable_pos, orient='index')
            df.to_excel(TRADEBOOK_EXCEL, index_label="Symbol")
        else:
            if os.path.exists(TRADEBOOK_EXCEL):
                os.remove(TRADEBOOK_EXCEL)  # Clean up if empty

    def log_history(self, symbol, pos_data, exit_price, exit_reason):
        file_exists = os.path.exists(TRADE_HISTORY_CSV)
        with open(TRADE_HISTORY_CSV, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(
                    ["Symbol", "Entry Date", "Exit Date", "Entry Price", "Exit Price", "Qty", "Reason", "PnL"])

            pnl = (exit_price - pos_data['entry_price']) * pos_data['qty']
            writer.writerow([
                symbol,
                pos_data['entry_time'],
                datetime.date.today(),
                pos_data['entry_price'],
                exit_price,
                pos_data['qty'],
                exit_reason,
                pnl
            ])
        log_event(f"📜 Trade logged to History: {symbol} | PnL: {pnl:.2f}", "success")

class EquityTracker:
    """Manages the Equity Curve Data"""
    def __init__(self):
        self.file = EQUITY_CURVE_JSON
        self.data = self.load()
    
    def load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r") as f:
                    return json.load(f)
            except:
                return []
        else:
            return [{"date": "2026-02-01", "equity": DEFAULT_FIXED_CAPITAL}]
    
    def update(self, current_equity):
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        if len(self.data) > 0 and self.data[-1]['date'] == today_str:
            self.data[-1]['equity'] = current_equity
        else:
            self.data.append({"date": today_str, "equity": current_equity})
        
        with open(self.file, "w") as f:
            json.dump(self.data, f, indent=4)


class LiveBot:
    def __init__(self, kite_instance):
        self.kite = kite_instance
        self.tb = TradeBookManager()  # Load existing trades
        self.equity_tracker = EquityTracker()
        self.positions = self.tb.positions
        self.instrument_map = self._get_instrument_map()
        self.today = datetime.date.today()
        self.blocked_stocks = {}
        self.stock_master_data = STOCK_MASTER_DATA
        self.strategy_engine = LiveStrategyEngine(self)
        
        # 🔹 AUTOMATIC RECONCILIATION ON STARTUP
        self.reconcile_with_broker()

    def log_event(self, msg, level="info"):
        """Wrapper for global log_event to fix Scheduler Error"""
        log_event(msg, level)

    def reconcile_with_broker(self):
        """
        ROBUST SYNC: Local TradeBook <-> Zerodha Broker Positions
        
        Logic:
        1. Fetch Holdings (Delivery)
        2. Fetch Positions (Intraday/BTST/Net)
        3. Merge: Net Qty = Holding Qty + Position Net Qty
        4. Sync with Local JSON:
           - Update Qty/Price for existing.
           - Add new positions (Default entry time: Today).
           - Remove ghosts (Local symbols not in Broker).
        5. Safety:
           - Retries on API failure.
           - Aborts if API returns error (Prevents wiping local data).
        """
        log_event("🔄 Starting Robust Broker Reconciliation...", "info")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 1. Fetch Data
                holdings = self.kite.holdings()
                positions = self.kite.positions()
                net_positions = positions.get("net", [])
                
                # 2. Build Broker Image
                broker_map = {}

                # A. Start with Holdings
                for h in holdings:
                    qty = int(h['quantity']) + int(h.get('t1_quantity', 0))
                    if qty == 0:
                        continue

                    symbol = f"{h['exchange']}-{h['tradingsymbol']}"
                    broker_map[symbol] = {
                        "qty": qty,
                        "avg_price": float(h['average_price']),
                        "src": "HOLDING"
                    }

                # B. Adjust with Net Positions (Intraday/BTST changes)
                for p in net_positions:
                    if p['product'] != self.kite.PRODUCT_CNC:
                        continue # We only track CNC equity
                    
                    qty = int(p['quantity'])
                    if qty == 0: continue
                    
                    symbol = f"{p['exchange']}-{p['tradingsymbol']}"
                    
                    if symbol in broker_map:
                        # Existing holding modified today
                        # Zerodha 'net' includes the holding qty if it was touched? 
                        # actually 'net' in positions is usually the day's net flow OR the net open position if carry forward.
                        # If a stock is in Holdings AND Positions:
                        # Holdings = T-1 settled qty.
                        # Positions = Today's checks.
                        # We need: Total = Holdings + Net Change of Day?
                        # Wait, Zerodha 'positions' API documentation says:
                        # "net": The net positions list.
                        # If I sell a holding, it shows in net with negative quantity?
                        # CORRECT LOGIC:
                        # If I have 100 shares in holding. I sell 50.
                        # Holdings: 100.
                        # Positions (Net): -50.
                        # Net Portfolio = 100 + (-50) = 50.
                        
                        # So we ADD net position qty to holding qty.
                        # BUT, sometimes Zerodha 'net' positions shows the *total* open position if it was a carry forward F&O.
                        # For Equity CNC:
                        # Holdings is settled.
                        # Positions is 'today'.
                        # If I sell 100 holdings (all), Positions = -100.
                        # Result = 0. Correct.
                        
                        # CAREFUL: If I bought today, it's NOT in holdings yet.
                        # It is in positions.
                        # So Add works.
                        
                        # If I hold 100. I buy 100 more.
                        # Holdings: 100. Positions: +100. Total = 200. Correct.
                        
                        broker_map[symbol]['qty'] += qty
                        
                        # Update Avg Price?
                        # If I buy more, avg price changes.
                        # Zerodha calculates this in 'average_price' of the net position?
                        # No, 'net' average price is for the day's trade.
                        # We should trust Zerodha's "Buy Average" from positions?
                        # Or just keep weighted avg?
                        # Simplest: If we have a position today, trust the 'average_price' from positions?
                        # No, that's only for today's trade.
                        # Computing true avg price of (Holdings + New) is complex without PnL api.
                        # For simplicity/safety: Keep existing holding avg price if we only sold.
                        # If we bought, utilize the logic:
                        # New Avg = ((Old Qty * Old Price) + (New Qty * New Price)) / Total
                        # But we don't know 'New Price' easily from just 'net'.
                        # Let's rely on the fact that if it's in broker_map, we use the holding price primarily,
                        # unless it was a fresh entry (not in holdings).
                        pass
                    else:
                        # New position today (Buy) OR Short (Intraday CNC? blocked usually)
                        broker_map[symbol] = {
                            "qty": qty,
                            "avg_price": float(p['average_price']),
                            "src": "POSITION"
                        }

                # C. Cleanup Zero Qty
                clean_map = {k: v for k, v in broker_map.items() if v['qty'] != 0}
                
                # 3. Sync with Local
                local_positions = self.tb.positions

                # 🔁 Build Local Tradingsymbol Mapping
                local_symbol_map = {}
                for sym in local_positions:
                    tradingsymbol = sym.split("-")[1]
                    local_symbol_map[tradingsymbol] = sym
                self.today = datetime.date.today()
                
                # A. Update / Add
                for symbol, b_data in clean_map.items():
                    b_qty = b_data['qty']
                    b_price = b_data['avg_price']
                    
                    tradingsymbol = symbol.split("-")[1]

                    if tradingsymbol in local_symbol_map:
                        old_key = local_symbol_map[tradingsymbol]
                        l_data = local_positions[old_key]

                        # 🔁 If exchange changed, rename key
                        if old_key != symbol:
                            log_event(f"🔁 Exchange switch detected: {old_key} → {symbol}", "warning")
                            local_positions[symbol] = local_positions.pop(old_key)
                            l_data = local_positions[symbol]

                        # ⚖️ Sync quantity
                        if l_data['qty'] != b_qty:
                            log_event(f"⚖️ Sync Qty {symbol}: {l_data['qty']} -> {b_qty}", "warning")
                            l_data['qty'] = b_qty

                        # Optional: update price only if source is HOLDING
                        if b_data['src'] == 'HOLDING':
                            if abs(l_data['entry_price'] - b_price) > 0.05:
                                l_data['entry_price'] = b_price
                                l_data['initial_entry_price'] = b_price

                    else:
                        # ADD New
                        log_event(f"➕ Found New Position: {symbol} Qty: {b_qty}", "warning")
                        local_positions[symbol] = {
                            "entry_price": b_price,
                            "entry_time": self.today, # New -> Today
                            "max_hold_days": TIME_STOP_BASE_DAYS,
                            "qty": b_qty,
                            "sl_price": b_price * 0.92,
                            "strategy": "Reconciled",
                            "pyramid_count": 0,
                            "partial_booked": False,
                            "initial_entry_price": b_price,
                            "initial_qty": b_qty
                        }

                # B. Remove Ghosts
                broker_tradingsymbols = set([k.split("-")[1] for k in clean_map])

                ghosts = [
                    s for s in list(local_positions.keys())
                    if s.split("-")[1] not in broker_tradingsymbols
                ]
                for s in ghosts:
                    log_event(f"❌ Removing Ghost: {s}", "warning")
                    del local_positions[s]
                
                # 4. Save
                self.tb.save()
                log_event("✅ Robust Reconciliation Complete.", "success")
                return # Success exit

            except Exception as e:
                log_event(f"⚠️ Reconciliation Failed (Attempt {attempt+1}/{max_retries}): {e}", "error")
                import time
                time.sleep(2)
        
        log_event("❌ CRITICAL: Reconciliation failed after retries. Local data NOT modified.", "error")

    def get_strategy_cash_wrapper(self):
        config = load_strategy_config()
        return self.get_strategy_cash(config)  

    def _get_instrument_map(self):
        log_event("Fetching Instrument Map...", "info")
        instruments = self.kite.instruments()
        mapping = {}
        for inst in instruments:
            key = f"{inst['exchange']}-{inst['tradingsymbol']}"
            mapping[key] = inst['instrument_token']
        return mapping

    def get_instrument_token(self, symbol):
        return self.instrument_map.get(symbol)

    def get_broker_cash(self):
        """Returns actual available cash from Zerodha"""
        try:
            margins = self.kite.margins(segment="equity")
            return float(margins['net'])
        except Exception as e:
            log_event(f"⚠️ Error fetching margins: {e}", "error")
            return 0.0 

    # [MODIFIED] Strategy cash calculation based on manual capital config
    def get_strategy_cash(self, config):
        real_cash = self.get_broker_cash()
        
        # Calculate current holdings value using latest prices if possible, or entry prices
        holdings_value = 0.0
        for sym, pos in self.positions.items():
            try:
                token = self.get_instrument_token(sym)
                ltp = self.kite.ltp(token)[str(token)]['last_price']
                holdings_value += pos['qty'] * ltp
            except:
                holdings_value += pos['qty'] * pos['entry_price']

        if config['mode'] == 'TOTAL_EQUITY':
            return real_cash
        else:
            # Fixed Capital logic
            strat_capital = config['fixed_capital']
            allowed_cash = strat_capital - holdings_value
            # Clamp between 0 and real_cash
            return max(0.0, min(allowed_cash, real_cash))

    # ==========================================
    # 4. LIVE DATA FETCHING
    # ==========================================

    def get_tech_data(self, symbol):
        token = self.get_instrument_token(symbol)
        if not token:
            print(f"❌ Token missing for {symbol}")
            return None

        to_date = datetime.datetime.now().date()
        from_date = to_date - datetime.timedelta(days=400)

        try:
            candles = self.kite.historical_data(token, from_date, to_date, "day")
            df = pd.DataFrame(candles)
        except Exception as e:
            print(f"⚠️ API Error fetching {symbol}: {e}")
            return None

        if len(df) < 201: return None

        curr = df.iloc[-1]
        closes = df['close'].values
        current_close = closes[-1]

        dma_50 = df['close'].rolling(50).mean().iloc[-1]
        dma_20 = df['close'].rolling(20).mean().iloc[-1]
        dma_200 = df['close'].rolling(200).mean().iloc[-1]
        avg_vol_20 = df['volume'].rolling(20).mean().iloc[-1]

        calc_df = df.tail(60).copy()
        calc_df['tr0'] = abs(calc_df['high'] - calc_df['low'])
        calc_df['tr1'] = abs(calc_df['high'] - calc_df['close'].shift())
        calc_df['tr2'] = abs(calc_df['low'] - calc_df['close'].shift())
        calc_df['tr'] = calc_df[['tr0', 'tr1', 'tr2']].max(axis=1)
        calc_df['atr'] = calc_df['tr'].rolling(14).mean()
        atr_val = calc_df['atr'].iloc[-1]
        atr_ma_20 = calc_df['atr'].rolling(20).mean().iloc[-1]

        delta = calc_df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        calc_df['rsi'] = 100 - (100 / (1 + rs))
        rsi_val = calc_df['rsi'].iloc[-1]

        prev_close = df.iloc[-2]['close']

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

        if sensex:
            latest_sensex['price'] = sensex['close']
            latest_sensex['change_pct'] = sensex['ret_1d']

        if nifty:
            latest_nifty['price'] = nifty['close']
            latest_nifty['change_pct'] = nifty['ret_1d']

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
            latest_sensex['regime'] = "Crash"
            return "Crash"
        elif "Trend" in (sensex_regime, nifty_regime):
            latest_sensex['regime'] = "Trend"
            return "Trend"
        else:
            latest_sensex['regime'] = "Sideways"
            return "Sideways"


    
    def calculate_portfolio_value(self):
        real_cash = self.get_broker_cash()
        
        holdings_value = 0.0
        for sym, pos in self.positions.items():
            try:
                 token = self.get_instrument_token(sym)
                 ltp = self.kite.ltp(token)[str(token)]['last_price']
                 holdings_value += ltp * pos['qty']
            except:
                 pass
        
        current_equity = real_cash + holdings_value
        self.equity_tracker.update(current_equity)
    def calculate_portfolio_value(self):
        real_cash = self.get_broker_cash()
        
        holdings_value = 0.0
        for sym, pos in self.positions.items():
            try:
                 token = self.get_instrument_token(sym)
                 ltp = self.kite.ltp(token)[str(token)]['last_price']
                 holdings_value += ltp * pos['qty']
            except:
                 pass
        
        current_equity = real_cash + holdings_value
        self.equity_tracker.update(current_equity)

    # ==========================================
    # 5. REAL ORDER EXECUTION
    # ==========================================

    def execute_broker_order(self, symbol, transaction_type, qty, tag):
        """Places actual order on Zerodha"""
        try:
            exchange = symbol.split("-")[0]
            tradingsymbol = symbol.split("-")[1]

            order_id = self.kite.place_order(
                tradingsymbol=tradingsymbol,
                exchange=exchange,
                transaction_type=transaction_type,
                quantity=qty,
                variety=self.kite.VARIETY_REGULAR,
                order_type=self.kite.ORDER_TYPE_MARKET,
                product=self.kite.PRODUCT_CNC,  
                validity=self.kite.VALIDITY_DAY,
                tag=tag
            )
            log_event(f"🚀 ORDER PLACED: {symbol} | {transaction_type} | Qty: {qty} | ID: {order_id}", "trade")
            return True
        except Exception as e:
            log_event(f"❌ ORDER FAILED: {symbol} | {e}", "error")
            return False

    def manage_orders(self, symbol, price, action="BUY", exit_reason=None, sl_price_input=0, strategy="Momentum",
                      quantity_override=0, risk_per_trade=RISK_PER_TRADE_PCT, signal_mult=1.0, is_high_vol=False):
        # Delegate to Strategy Engine
        return self.strategy_engine.manage_orders(
            symbol, price, action, exit_reason, sl_price_input, strategy,
            quantity_override, risk_per_trade, signal_mult, is_high_vol
        )

    # ==========================================
    # 6. MAIN STRATEGY LOGIC
    # ==========================================

    def run_cycle(self, only_manage=False):
        self.calculate_portfolio_value()

        # If only managing positions, DO NOT scan full universe
        if only_manage:
            return

        # Only run full strategy when allowed (3:05 PM)
        self.strategy_engine.run_strategy()

# ==========================================
# 7. WEB SERVER & SCHEDULER (UI HANDLING)
# ==========================================
async def daily_token_reset_task():
    """
    Resets system state at 07:00 AM daily.
    - Invalidates all sessions.
    - Clears in-memory bots.
    - Marks system as disconnected.
    """
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        
        if now > target_time:
            target_time += datetime.timedelta(days=1)
        
        wait_seconds = (target_time - now).total_seconds()
        log_event(f"⏳ Next Token Reset scheduled in {wait_seconds/3600:.2f} hours (at 07:00 AM)", "info")
        
        await asyncio.sleep(wait_seconds)
        
        # 🟢 EXECUTE RESET
        log_event("🔄 Executing Daily Token Reset...", "warning")
        
        try:
            # 1. Clear Sessions
            ACCESS_SESSIONS.clear()
            
            # 2. Reset System Status
            global system_status
            system_status["connected"] = False
            system_status["regime"] = "Unknown"
            
            # 3. Clear Active Bot Instances (Garbage Collection hint)
            global _legacy_bot
            _legacy_bot = None
            
            log_event("✅ Daily Reset Completed. Waiting for new token...", "success")
            
            # Sleep a bit to avoid double execution in case of ms precision issues
            await asyncio.sleep(60) 

        except Exception as e:
            log_event(f"❌ Error during Daily Reset: {e}", "error")
            await asyncio.sleep(60)

async def access_token_watcher():
    """
    Monitors for today's access token file.
    - If found: Auto-initializes the bot.
    - If not found: Keeps checking.
    """
    while True:
        now = datetime.datetime.now()
        today_str = now.date().strftime("%Y-%m-%d")

        # 1. Check if we are already connected?
        # If connected, we might still want to check if token file changed? 
        # For now, if connected, just rely on health check or session expiry.
        # But requirement says: "If today's file is generated, auto-initialize bot"
        
        if system_status["connected"]:
             await asyncio.sleep(300) # Check every 5 mins if already connected
             continue

        # 2. Look for today's token file
        if today_access_token_exists():
            try:
                # Load Token
                token_file = os.path.join(ACCESS_TOKEN_DIR, f"{today_str}.json")
                with open(token_file, "r") as f:
                    access_token = json.load(f)
                
                log_event(f"📂 Found Access Token for {today_str}. Auto-logging in...", "info")
                
                # Initialize Kite & Bot
                kite = KiteConnect(api_key=API_KEY)
                kite.set_access_token(access_token)
                
                # Create a System Session (since no user triggered this)
                # Or just assign to a global bot instance?
                # The architecture uses ACCESS_SESSIONS. We need a "system" session or similar.
                # Let's create a special 'AUTO_BOT' session.
                
                session_id = f"AUTO-SESSION-{today_str}"
                
                bot = LiveBot(kite)
                
                ACCESS_SESSIONS[session_id] = {
                    "created_at": datetime.datetime.utcnow(),
                    "ip": "127.0.0.1",
                    "user_agent": "System/AutoLogin",
                    "kite": kite,
                    "bot": bot
                }
                
                system_status["connected"] = True
                log_event("✅ Auto login via access token successful.", "success")
                
                # Trigger Reconciliation immediately
                bot.reconcile_with_broker()
                
            except Exception as e:
                 log_event(f"❌ Auto-login failed: {e}", "error")
        else:
            # Token not found yet
            # Log only periodically to avoid spam
            if now.minute % 10 == 0:
                 log_event("🔍 Waiting for today's access token...", "info")
        
        await asyncio.sleep(120)  # Check every 2 minutes

async def index_ticker_task():
    while True:
        # [MODIFIED] Dynamic Lookup
        active_bot = get_current_active_bot()
        
        if active_bot and system_status["connected"]:
            try:
                s_token = active_bot.get_instrument_token("BSE-SENSEX")
                n_token = active_bot.get_instrument_token("NSE-NIFTY 50")
                
                if s_token and n_token:
                    quotes = active_bot.kite.quote([s_token, n_token])
                    
                    if str(s_token) in quotes:
                        q = quotes[str(s_token)]
                        latest_sensex['price'] = q['last_price']
                        prev = q['ohlc']['close']
                        latest_sensex['change_pct'] = ((q['last_price'] - prev) / prev) * 100
                        
                    if str(n_token) in quotes:
                        q = quotes[str(n_token)]
                        latest_nifty['price'] = q['last_price']
                        prev = q['ohlc']['close']
                        latest_nifty['change_pct'] = ((q['last_price'] - prev) / prev) * 100
                        
            except Exception as e:
                pass
        
        await asyncio.sleep(1) 

async def scheduler_task():
    last_scan_date = None
    while True:
        # [MODIFIED] Dynamic Lookup
        active_bot = get_current_active_bot()

        if active_bot:
            now = datetime.datetime.now()
            t_curr = now.time()

            start_time = datetime.time(9, 15) 
            end_time = datetime.time(15, 30)
            scan_time_start = datetime.time(15, 20)  
            scan_time_end = datetime.time(15, 30)  

            if start_time <= t_curr <= end_time:

                run_full_scan = False

                if scan_time_start <= t_curr < scan_time_end:
                    if last_scan_date != now.date():
                        log_event("⏰ IT IS 3:20 PM. RUNNING FULL SCAN & ENTRY.", "info")
                        run_full_scan = True
                        last_scan_date = now.date()

                try:
                    # [MODIFIED] Dynamic Lookup
                    active_bot = get_current_active_bot()
                    if active_bot:
                        if run_full_scan:
                            active_bot.run_cycle(only_manage=False)  
                        else:
                            active_bot.run_cycle(only_manage=True)
                except Exception as e:
                    # Catch ALL exceptions from strategy engine to keep scheduler alive
                    log_event(f"❌ CRITICAL Scheduler Error: {e}", "error")
                    import traceback
                    traceback.print_exc()

            else:
                pass
            
        await asyncio.sleep(60) 

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler_task())
    asyncio.create_task(index_ticker_task())
    asyncio.create_task(daily_token_reset_task()) # 🟢 Added Daily Reset
    asyncio.create_task(access_token_watcher())

# ==========================================
# 🔐 AUTH & SESSION MANAGEMENT
# ==========================================


@app.get("/auth/login-page")
def login_page():
    return FileResponse("static/login.html")

@app.post("/auth/login")
def user_login(response: Response, username: str, password: str, request: Request):
    if not verify_user(username, password):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    session_id = str(uuid4())

    ACCESS_SESSIONS[session_id] = {
        "created_at": datetime.datetime.utcnow(),
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "kite": None,
        "bot": None
    }

    # 🔥 ENV-AWARE COOKIE SETTINGS
    is_localhost = request.url.hostname in ("localhost", "127.0.0.1")

    response.set_cookie(
        key="access_session",
        value=session_id,
        httponly=True,
        secure=not is_localhost,
        samesite="lax" if is_localhost else "none",
        domain=None # Defaulting to None allows it to work dynamically on Railway and Vercel hostnames
    )

    return {"status": "ok", "msg": "Authenticated"}

@app.get("/login")
def login_redirect(request: Request):
     # Check if session exists from middleware binding
     # But middleware might have ALREADY redirected if not logged in.
     # If we are here, we are logged in.
     return RedirectResponse("/login/zerodha")

@app.get("/login/zerodha")
def zerodha_login(request: Request):
    # Middleware guarantees session exists
    kite = KiteConnect(api_key=API_KEY)
    return RedirectResponse(kite.login_url())

@app.get("/kite/callback")
def kite_callback(request_token: str, request: Request):
    global system_status

    session_id = request.cookies.get("access_session")
    if not session_id:
        log_event("❌ Kite Callback Failed: 'access_session' cookie is MISSING from the request. Check your Zerodha Redirect URL.", "error")
        return {"error": "Kite Callback Failed: Cookie Missing. Make sure you access the site via HTTPS and the Zerodha Redirect URL perfectly matches."}

    session = ACCESS_SESSIONS.get(session_id)
    if not session:
        log_event("❌ Kite Callback Failed: The in-memory session was wiped! Railway container might have restarted during your login.", "error")
        return {"error": "Kite Callback Failed: Session wiped due to server restart. Please log in again."}

    try:
        kite = KiteConnect(api_key=API_KEY)
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        token = data["access_token"]

        if not os.path.exists("AccessToken"):
            os.makedirs("AccessToken")

        with open(f"AccessToken/{datetime.datetime.now().date()}.json", "w") as f:
            json.dump(token, f)

        kite.set_access_token(token)
        # Bind bot to THIS session
        bot = LiveBot(kite)
        ACCESS_SESSIONS[session_id]["kite"] = kite
        ACCESS_SESSIONS[session_id]["bot"] = bot

        system_status["connected"] = True
        log_event("✅ Bot Initialized via Web Login (Session Bound)", "success")

        return RedirectResponse("/dashboard", status_code=302)

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/refresh_token")
def refresh_token():
    """
    Manually invalidates the current session and forces a UI redirect for re-login.
    """
    global system_status
    ACCESS_SESSIONS.clear()
    system_status["connected"] = False
    log_event("🔄 Manual token refresh triggered", "warning")
    return {"status": "success", "msg": "Token invalidated. Please re-login."}



@app.get("/status")
def get_status(request: Request):
    global kill_switch_active
    
    bot_ref = request.state.session.get("bot") or get_current_active_bot()

    if bot_ref:
        try:
            regime = bot_ref.get_sensex_regime()
            system_status["regime"] = regime
        except:
            pass

    return {
        "connected": system_status["connected"],
        "regime": system_status.get("regime", "Unknown"),
        "kill_switch": kill_switch_active
    }

@app.get("/sensex")
def get_sensex():
    return latest_sensex

@app.get("/nifty")
def get_nifty():
    return latest_nifty

@app.get("/positions")
def get_positions(request: Request):
    bot_instance = request.state.session.get("bot") or get_current_active_bot()
    if not bot_instance: return []
    pos_list = []
    for sym in bot_instance.positions:
        try:
            token = bot_instance.get_instrument_token(sym)
            quote = bot_instance.kite.ltp(token)
            ltp = quote[str(token)]['last_price']
        except:
            ltp = bot_instance.positions[sym]['entry_price'] 
            
        p_data = bot_instance.positions[sym]
        pos_list.append({
            "symbol": sym,
            "qty": p_data['qty'],
            "avg": p_data['entry_price'],
            "ltp": ltp,
            "days": (datetime.date.today() - p_data['entry_time']).days,
            "maxDays": p_data['max_hold_days'],
            "signal": "Active"
        })
    return pos_list

@app.get("/logs")
def get_logs():
    return list(log_buffer)

@app.post("/exit/{symbol}")
def force_exit(symbol: str, request: Request):
    bot_instance = request.state.session.get("bot") or get_current_active_bot()
    if not bot_instance: return {"status": "error", "msg": "Bot not connected"}
    try:
        token = bot_instance.get_instrument_token(symbol)
        quote = bot_instance.kite.ltp(token)
        ltp = quote[str(token)]['last_price']
        
        success = bot_instance.manage_orders(symbol, ltp, "SELL", exit_reason="MANUAL_API")
        if success:
            return {"status": "success", "msg": f"Exited {symbol}"}
        else:
            return {"status": "error", "msg": "Exit failed"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


# ----------------------------------------------------
# MODIFIED/NEW ENDPOINTS FOR CAPITAL CONTROL & UI DATA
# ----------------------------------------------------

class CapitalUpdate(BaseModel):
    mode: str
    amount: float

@app.post("/update_capital")
def update_capital(data: CapitalUpdate):
    if data.mode not in ["TOTAL_EQUITY", "FIXED"]:
        return JSONResponse(status_code=400, content={"error": "Invalid mode"})
    
    config = load_strategy_config()
    config['mode'] = data.mode
    config['fixed_capital'] = data.amount
    save_strategy_config(config)
    log_event(f"⚙️ Strategy Capital Updated: {data.mode} | Amt: {data.amount}", "info")
    return {"status": "success", "config": config}

@app.get("/config")
def get_config(request: Request):
    # [MODIFIED] Return all details required for UI (cash, equity, positions value, etc)
    config = load_strategy_config()
    
    live_broker_cash = DEFAULT_FIXED_CAPITAL
    holdings_value = 0.0

    bot_ref = request.state.session.get("bot") or get_current_active_bot()

    if bot_ref and system_status["connected"]:
        live_broker_cash = bot_ref.get_broker_cash()
        
        for sym, pos in bot_ref.positions.items():
            try:
                token = bot_ref.get_instrument_token(sym)
                ltp = bot_ref.kite.ltp(token)[str(token)]['last_price']
                holdings_value += ltp * pos['qty']
            except:
                holdings_value += pos['entry_price'] * pos['qty']
                
    total_account_equity = live_broker_cash + holdings_value

    if config['mode'] == 'TOTAL_EQUITY':
        strategy_capital = total_account_equity
        strategy_cash_available = live_broker_cash
    else:
        strategy_capital = config['fixed_capital']
        strategy_cash_available = max(0.0, min(strategy_capital - holdings_value, live_broker_cash))

    return {
        "risk_per_trade": RISK_PER_TRADE_PCT,
        "max_positions": MOMENTUM_MAX_OPEN_POS,
        "pyramid_limit": PYRAMID_MAX_ADDS,
        "mode": config['mode'],
        "configured_capital": config['fixed_capital'],
        "real_broker_cash": live_broker_cash,
        "current_holdings_value": holdings_value,
        "total_account_equity": total_account_equity,
        "strategy_cash_available": strategy_cash_available,
        "strategy_effective_capital": strategy_capital
    }

@app.get("/history")
def get_history():
    if not os.path.exists(TRADE_HISTORY_CSV): return []
    try:
        data = []
        with open(TRADE_HISTORY_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return list(reversed(data)) 
    except:
        return []

@app.get("/performance")
def get_performance_curve():
    if os.path.exists(EQUITY_CURVE_JSON):
        try:
            with open(EQUITY_CURVE_JSON, 'r') as f:
                return json.load(f)
        except:
            return []
    return [{"date": "2026-02-01", "equity": DEFAULT_FIXED_CAPITAL}]

@app.get("/signals")
def get_signal_queue():
    return scan_results

@app.post("/kill")
def toggle_kill_switch(active: bool):
    global kill_switch_active
    kill_switch_active = active
    msg = "STOPPED" if active else "RESUMED"
    log_event(f"🚨 EMERGENCY KILL SWITCH {msg}", "error" if active else "success")
    return {"status": "success", "kill_active": kill_switch_active}

@app.get("/user")
def get_user_profile():
    return {
        "name": "Parth Jhalaria",
        "institution": "IIM Bodh Gaya",
        "role": "Algo Trader / Developer",
        "account_id": "ZERODHA_KITE_ID" 
    }

# ==========================================
# 8. TERMINAL GENERATION (NEW FEATURE)
# ==========================================

def generate_terminal_html():
    try:
        excel_filename = "Indices_Daily_Prices_2016_2026.xlsx"
        if not os.path.exists(excel_filename):
            print(f"⚠️ Excel file {excel_filename} not found.")
            return

        df = pd.read_excel(excel_filename, sheet_name="Sheet1")

        # Clean the Date column
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        # Get list of indices (excluding Date and My Algo)
        indices = [col for col in df.columns if col not in ['Date', 'My Algo']]

        # Convert dataframe to JSON
        data_json = df.to_json(orient='records')
        indices_json = json.dumps(indices)

        # ==========================================
        # GENERATE ADVANCED TERMINAL HTML
        # ==========================================
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QUANT_DESK // PRO TERMINAL</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0e14;
            --bg-panel: #151924;
            --bg-header: #1e222d;
            --border: #2a2e39;
            --text-main: #d1d4dc;
            --text-dim: #787b86;
            --accent: #2962ff;
            --up: #26a69a;
            --down: #ef5350;
            --algo: #00bcd4; /* Cyan for Algo */
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg-base); color: var(--text-main); height: 100vh; overflow: hidden; display: flex; flex-direction: column; font-size: 13px; }}

        /* Top Navigation Bar */
        .top-bar {{ background: var(--bg-header); height: 50px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; flex-shrink: 0; }}
        .brand {{ display: flex; align-items: center; font-weight: 600; font-size: 1.1rem; letter-spacing: 0.5px; }}
        .pulse {{ width: 8px; height: 8px; background: var(--up); border-radius: 50%; margin-right: 12px; box-shadow: 0 0 10px var(--up); animation: blink 2s infinite; }}
        @keyframes blink {{ 50% {{ opacity: 0.3; }} }}
        .clock {{ font-family: 'JetBrains Mono', monospace; color: var(--text-dim); }}

        /* Main Workspace Grid */
        .workspace {{ display: grid; grid-template-columns: 300px 1fr; grid-template-rows: 1fr 220px; height: calc(100vh - 50px); width: 100vw; }}

        /* Shared Panel Styles */
        .panel {{ background: var(--bg-panel); border: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden; }}
        .panel-header {{ height: 40px; border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 15px; font-weight: 600; font-size: 0.85rem; color: var(--text-dim); background: rgba(0,0,0,0.2); }}

        /* Left Sidebar (Asset Browser) */
        .sidebar {{ grid-row: 1 / 3; border-right: 1px solid var(--border); }}
        .search-box {{ padding: 10px; border-bottom: 1px solid var(--border); }}
        .search-box input {{ width: 100%; background: #0b0e14; border: 1px solid var(--border); color: var(--text-main); padding: 8px 12px; border-radius: 4px; font-family: 'Inter', sans-serif; outline: none; }}
        .search-box input:focus {{ border-color: var(--accent); }}
        .asset-list {{ overflow-y: auto; flex-grow: 1; }}
        .asset-list::-webkit-scrollbar {{ width: 4px; }}
        .asset-list::-webkit-scrollbar-thumb {{ background: var(--border); }}

        .asset-item {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; border-bottom: 1px solid rgba(42,46,57,0.5); cursor: pointer; transition: 0.1s; }}
        .asset-item:hover {{ background: rgba(255,255,255,0.03); }}
        .asset-item.active {{ background: rgba(41, 98, 255, 0.1); border-left: 3px solid var(--accent); }}
        .asset-item.algo-row {{ border-left: 3px solid var(--algo); }}
        
        .asset-name {{ font-weight: 500; display: flex; align-items: center; gap: 8px; }}
        .color-dot {{ width: 14px; height: 14px; border-radius: 50%; cursor: pointer; border: 2px solid var(--bg-panel); box-shadow: 0 0 0 1px var(--border); }}

        /* Main Chart Area */
        .chart-area {{ grid-column: 2; grid-row: 1; position: relative; }}
        .toolbar {{ display: flex; align-items: center; gap: 4px; padding: 10px 15px; border-bottom: 1px solid var(--border); }}
        .btn-time {{ background: transparent; border: 1px solid transparent; color: var(--text-dim); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-family: 'Inter', sans-serif; font-weight: 500; font-size: 0.8rem; transition: 0.2s; }}
        .btn-time:hover {{ color: #fff; background: rgba(255,255,255,0.05); }}
        .btn-time.active {{ background: var(--accent); color: #fff; box-shadow: 0 2px 10px rgba(41,98,255,0.3); }}

        #chart-container {{ height: calc(100% - 60px); width: 100%; position: relative; }}
        
        /* Drag ROI Readout */
        #measure-box {{ position: absolute; top: 15px; left: 15px; background: rgba(11, 14, 20, 0.85); backdrop-filter: blur(5px); border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-family: 'JetBrains Mono', monospace; z-index: 10; display: none; box-shadow: 0 4px 15px rgba(0,0,0,0.5); font-size: 0.8rem; min-width: 200px; }}
        .measure-title {{ color: var(--text-dim); font-size: 0.75rem; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}

        /* Bottom Analytics Panel */
        .analytics-area {{ grid-column: 2; grid-row: 2; border-top: 1px solid var(--border); overflow-y: auto; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }}
        .data-table th {{ position: sticky; top: 0; background: var(--bg-header); color: var(--text-dim); font-weight: 600; text-align: right; padding: 10px 15px; border-bottom: 1px solid var(--border); font-family: 'Inter', sans-serif; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }}
        .data-table th:first-child {{ text-align: left; }}
        .data-table td {{ padding: 12px 15px; text-align: right; border-bottom: 1px solid rgba(42,46,57,0.5); }}
        .data-table td:first-child {{ text-align: left; color: var(--text-main); font-weight: 500; display: flex; align-items: center; gap: 8px; font-family: 'Inter', sans-serif; }}
        .up {{ color: var(--up); }}
        .down {{ color: var(--down); }}

        /* Hidden inputs for color pickers */
        .hidden-color {{ position: absolute; opacity: 0; width: 0; height: 0; }}
    </style>
</head>
<body>

    <header class="top-bar">
        <div class="brand"><div class="pulse"></div>QUANT_DESK // V2.PRO</div>
        <div style="display: flex; gap: 20px; align-items: center;">
            <a href="/dashboard"> style="text-decoration: none; color: var(--text-dim); font-weight: 500; font-size: 0.85rem; border: 1px solid var(--border); padding: 5px 12px; border-radius: 4px; transition: 0.2s;" onmouseover="this.style.color='#fff'; this.style.borderColor='var(--accent)'" onmouseout="this.style.color='var(--text-dim)'; this.style.borderColor='var(--border)'">
                <span style="font-family: 'Inter', sans-serif;">&larr; DASHBOARD</span>
            </a>
            <div class="clock" id="live-clock">00:00:00 UTC</div>
        </div>
    </header>

    <div class="workspace">
        <aside class="panel sidebar">
            <div class="panel-header">ASSET NAVIGATOR</div>
            <div class="search-box">
                <input type="text" id="asset-search" placeholder="Filter indices..." onkeyup="filterAssets()">
            </div>
            <div class="asset-list" id="asset-list">
                <div class="asset-item active algo-row" onclick="toggleIndex('My Algo', this)">
                    <div class="asset-name">
                        <input type="color" class="hidden-color" id="color-My Algo" value="#00bcd4" onchange="changeColor('My Algo', this.value)">
                        <div class="color-dot" style="background: #00bcd4;" onclick="triggerColor('My Algo', event)"></div>
                        My Algo [Proprietary]
                    </div>
                </div>
            </div>
        </aside>

        <main class="panel chart-area">
            <div class="toolbar" id="time-filters">
                <button class="btn-time" onclick="setTime('1m')">1M</button>
                <button class="btn-time" onclick="setTime('3m')">3M</button>
                <button class="btn-time" onclick="setTime('6m')">6M</button>
                <button class="btn-time" onclick="setTime('12m')">1Y</button>
                <button class="btn-time" onclick="setTime('3y')">3Y</button>
                <button class="btn-time" onclick="setTime('5y')">5Y</button>
                <button class="btn-time" onclick="setTime('10y')">10Y</button>
                <button class="btn-time active" onclick="setTime('all')">MAX</button>
                <span style="margin-left:auto; color:var(--text-dim); font-size:0.8rem; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px;">Click & Drag on chart to measure ROI</span>
            </div>
            <div id="chart-container">
                <div id="measure-box"></div>
                <div id="chart"></div>
            </div>
        </main>

        <section class="panel analytics-area">
            <div class="panel-header">ADVANCED METRICS (Selected Period)</div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Start Value</th>
                        <th>End Value</th>
                        <th>Total ROI %</th>
                        <th>CAGR %</th>
                        <th>Est. Volatility</th>
                    </tr>
                </thead>
                <tbody id="metrics-body"></tbody>
            </table>
        </section>
    </div>

<script>
    // System Clock
    setInterval(() => document.getElementById('live-clock').innerText = new Date().toUTCString(), 1000);

    const rawData = {data_json};
    const allIndices = {indices_json};
    
    let selectedIndices = ['My Algo', 'NIFTY 50', 'SENSEX']; 
    let selectedTime = 'all';
    let chart = null;

    // Premium Color Palette
    const palette = ['#2962ff', '#ef5350', '#26a69a', '#ab47bc', '#ff9800', '#7e57c2', '#ff5252'];
    const colorMap = {{ 'My Algo': '#00bcd4' }};

    function initUI() {{
        const container = document.getElementById('asset-list');
        allIndices.forEach((idx, i) => {{
            colorMap[idx] = palette[i % palette.length];
            const isActive = selectedIndices.includes(idx);
            
            const div = document.createElement('div');
            div.className = `asset-item ${{isActive ? 'active' : ''}}`;
            div.dataset.index = idx;
            div.onclick = () => toggleIndex(idx, div);
            
            div.innerHTML = `
                <div class="asset-name">
                    <input type="color" class="hidden-color" id="color-${{idx.replace(/\\s/g, '-')}}" value="${{colorMap[idx]}}" onchange="changeColor('${{idx}}', this.value)">
                    <div class="color-dot" style="background: ${{colorMap[idx]}};" onclick="triggerColor('${{idx}}', event)"></div>
                    ${{idx}}
                </div>
            `;
            container.appendChild(div);
        }});
        updateDashboard();
    }}

    // Filter list
    function filterAssets() {{
        const term = document.getElementById('asset-search').value.toLowerCase();
        document.querySelectorAll('.asset-item').forEach(item => {{
            item.style.display = item.innerText.toLowerCase().includes(term) ? 'flex' : 'none';
        }});
    }}

    function triggerColor(idx, event) {{
        event.stopPropagation();
        document.getElementById(`color-${{idx.replace(/\\s/g, '-')}}`).click();
    }}

    function changeColor(idx, newColor) {{
        colorMap[idx] = newColor;
        document.querySelector(`[data-index="${{idx}}"] .color-dot`).style.background = newColor;
        if(idx === 'My Algo') document.querySelector('.algo-row .color-dot').style.background = newColor;
        updateDashboard(); 
    }}

    function toggleIndex(idx, el) {{
        if (selectedIndices.includes(idx)) {{
            selectedIndices = selectedIndices.filter(i => i !== idx);
            el.classList.remove('active');
        }} else {{
            selectedIndices.push(idx);
            el.classList.add('active');
        }}
        updateDashboard();
    }}

    function setTime(timeStr) {{
        selectedTime = timeStr;
        document.querySelectorAll('#time-filters .btn-time').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');
        updateDashboard();
    }}

    function getStandardDeviation(array) {{
        const n = array.length;
        if (n <= 1) return 0;
        const mean = array.reduce((a, b) => a + b) / n;
        return Math.sqrt(array.map(x => Math.pow(x - mean, 2)).reduce((a, b) => a + b) / (n - 1));
    }}

    function updateDashboard() {{
        const lastDate = new Date(rawData[rawData.length - 1].Date);
        let startDate = new Date("1900-01-01"); 

        if (selectedTime !== 'all') {{
            startDate = new Date(lastDate);
            if (selectedTime === '1m') startDate.setMonth(lastDate.getMonth() - 1);
            if (selectedTime === '3m') startDate.setMonth(lastDate.getMonth() - 3);
            if (selectedTime === '6m') startDate.setMonth(lastDate.getMonth() - 6);
            if (selectedTime === '12m') startDate.setFullYear(lastDate.getFullYear() - 1);
            if (selectedTime === '3y') startDate.setFullYear(lastDate.getFullYear() - 3);
            if (selectedTime === '5y') startDate.setFullYear(lastDate.getFullYear() - 5);
            if (selectedTime === '10y') startDate.setFullYear(lastDate.getFullYear() - 10);
        }}

        const filteredData = rawData.filter(d => new Date(d.Date) >= startDate);
        if (filteredData.length === 0) return;

        const firstRow = filteredData[0];
        const lastRow = filteredData[filteredData.length - 1];
        
        // Calculate diff in years for CAGR
        const diffYears = (new Date(lastRow.Date) - new Date(firstRow.Date)) / (1000 * 60 * 60 * 24 * 365.25);
        
        const seriesData = [];
        const tableRows = [];
        const currentColors = [];

        // Put My Algo first in order
        const columnsToPlot = selectedIndices.slice();
        if(!columnsToPlot.includes('My Algo')) columnsToPlot.unshift('My Algo');

        columnsToPlot.forEach(col => {{
            if (!selectedIndices.includes(col)) return;

            const baseValue = firstRow[col];
            const endValue = lastRow[col];
            const returnsData = [];
            const dataPts = [];

            filteredData.forEach(d => {{
                const val = (d[col] / baseValue) * 10;
                dataPts.push([new Date(d.Date).getTime(), val]);
                returnsData.push(d[col]);
            }});

            seriesData.push({{ name: col, data: dataPts }});
            currentColors.push(colorMap[col]);

            // Analytics calculations
            const roi = ((endValue - baseValue) / baseValue) * 100;
            const cagr = diffYears > 0 ? (Math.pow(endValue / baseValue, 1 / diffYears) - 1) * 100 : 0;
            
            // Daily returns for vol
            const dailyReturns = [];
            for(let i=1; i<returnsData.length; i++) {{
                dailyReturns.push((returnsData[i] - returnsData[i-1])/returnsData[i-1]);
            }}
            const stdDev = getStandardDeviation(dailyReturns);
            const annVol = stdDev * Math.sqrt(252) * 100; // Annualized Volatility

            tableRows.push({{ col, baseValue, endValue, roi, cagr, annVol }});
        }});

        updateChart(seriesData, currentColors);
        updateTable(tableRows);
    }}

    function formatPct(val) {{
        const sign = val >= 0 ? '+' : '';
        const clr = val >= 0 ? 'up' : 'down';
        return `<span class="${{clr}}">${{sign}}${{val.toFixed(2)}}%</span>`;
    }}

    function updateTable(rows) {{
        const tbody = document.getElementById('metrics-body');
        tbody.innerHTML = '';
        rows.forEach(r => {{
            tbody.innerHTML += `
                <tr>
                    <td><div class="color-dot" style="background:${{colorMap[r.col]}}"></div> ${{r.col}}</td>
                    <td>10.00</td>
                    <td>${{(r.endValue / r.baseValue * 10).toFixed(2)}}</td>
                    <td>${{formatPct(r.roi)}}</td>
                    <td>${{formatPct(r.cagr)}}</td>
                    <td>${{r.annVol.toFixed(2)}}%</td>
                </tr>
            `;
        }});
        document.getElementById('measure-box').style.display = 'none';
    }}

    // Advanced Drag ROI
    function calcSelectionROI(minTs, maxTs) {{
        const startData = rawData.find(d => new Date(d.Date).getTime() >= minTs);
        const endData = rawData.slice().reverse().find(d => new Date(d.Date).getTime() <= maxTs);
        if(!startData || !endData) return;

        let html = `<div class="measure-title">MEASURE: ${{startData.Date}} to ${{endData.Date}}</div>`;
        selectedIndices.forEach(col => {{
            const roi = ((endData[col] - startData[col]) / startData[col]) * 100;
            html += `<div style="display:flex; justify-content:space-between; margin-top:5px;">
                        <span style="color:${{colorMap[col]}}">${{col}}</span>
                        <span>${{formatPct(roi)}}</span>
                     </div>`;
        }});
        
        const box = document.getElementById('measure-box');
        box.innerHTML = html;
        box.style.display = 'block';
    }}

    function updateChart(series, colors) {{
        const options = {{
            series: series,
            chart: {{ 
                type: 'area', height: '100%', fontFamily: 'JetBrains Mono, monospace',
                background: 'transparent', theme: {{ mode: 'dark' }},
                toolbar: {{ tools: {{ zoom: true, selection: true, pan: true }} }},
                animations: {{ enabled: false }},
                events: {{ zoomed: (ctx, {{xaxis}}) => {{ if(xaxis.min) calcSelectionROI(xaxis.min, xaxis.max); }} }}
            }},
            colors: colors,
            fill: {{
                type: series.map(s => s.name === 'My Algo' ? 'gradient' : 'solid'),
                gradient: {{ shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05, stops: [0, 100] }},
                opacity: series.map(s => s.name === 'My Algo' ? 0.3 : 0) // Only Algo gets filled
            }},
            stroke: {{ width: series.map(s => s.name === 'My Algo' ? 3 : 1.5), curve: 'straight' }},
            grid: {{ borderColor: '#2a2e39', strokeDashArray: 2, xaxis: {{ lines: {{ show: true }} }}, yaxis: {{ lines: {{ show: true }} }} }},
            xaxis: {{ type: 'datetime', labels: {{ style: {{ colors: '#787b86' }} }}, tooltip: {{ enabled: false }} }},
            yaxis: {{ labels: {{ formatter: v => v.toFixed(2), style: {{ colors: '#787b86' }} }}, opposite: true }},
            legend: {{ show: false }}, // Handled by table/sidebar
            tooltip: {{ theme: 'dark', x: {{ format: 'dd MMM yyyy' }} }},
            dataLabels: {{ enabled: false }}
        }};

        if (chart) chart.destroy();
        chart = new ApexCharts(document.querySelector("#chart"), options);
        chart.render();
    }}

    initUI();
</script>
</body>
</html>
"""

        output_file = "static/terminal_pro.html"
        if not os.path.exists("static"): os.makedirs("static")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_template)

        print(f"✅ QUANT_DESK // V2.PRO Generated as '{output_file}'.")
    except Exception as e:
        print(f"⚠️ Error generating terminal: {e}")

@app.get("/update_terminal")
def update_terminal_endpoint():
    try:
        generate_terminal_html()
        return {"status": "success", "msg": "Terminal updated"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@app.on_event("startup")
async def generate_terminal_on_start():
    try:
        generate_terminal_html()
    except Exception as e:
        print(f"Error generating terminal on startup: {e}")

if __name__ == "__main__":
   
    print("🚀 Server starting on port 8000...")
    print("👉 Open http://localhost:8000/dashboard in your browser (Login: admin/admin123)")
    uvicorn.run(app, host="0.0.0.0", port=8000)