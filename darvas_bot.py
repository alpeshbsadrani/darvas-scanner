import pandas as pd
import yfinance as yf
import requests
import warnings
import math
from datetime import datetime

warnings.filterwarnings('ignore')

# --- તમારી વિગતો ---
TELEGRAM_BOT_TOKEN = '8896031421:AAFIeqDTKsH64aAnaCuiuW8F9aZxMTIEA9g'
TELEGRAM_CHAT_ID = '1051774043'

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1eKumGC4e2MV1jPjoG3LvOtvJ24SKUz2Y5YPkO5WUPlQ/export?format=csv'

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_stocks_from_sheet():
    try:
        df = pd.read_csv(SHEET_URL + '&t=' + str(datetime.now().timestamp()))
        stocks = df.iloc[:, 0].dropna().tolist()
        clean_stocks = []
        for s in stocks:
            sym = str(s).strip()
            if sym != '':
                if not sym.endswith('.NS') and not sym.endswith('.BO'):
                    sym += '.NS'
                clean_stocks.append(sym)
        return clean_stocks
    except Exception as e:
        print(f"ગૂગલ શીટ વાંચવામાં એરર: {e}")
        return []

def calculate_car_status(series_close):
    """CAR Status Calculation"""
    if len(series_close) < 200:
        return "SHORT HISTORY"
    
    sma50 = series_close.rolling(50).mean().dropna()
    sma200 = series_close.rolling(200).mean().dropna()

    if len(sma50) == 0 or len(sma200) < 21:
        return "SHORT HISTORY"

    cmp = float(series_close.iloc[-1])
    val_sma50 = float(sma50.iloc[-1])
    val_sma200 = float(sma200.iloc[-1])
    prev_sma200 = float(sma200.iloc[-21])

    if cmp > val_sma50 and cmp > val_sma200 and val_sma200 >= prev_sma200:
        return "BUY / AVERAGE"
    else:
        return "AVOID"

def analyze_stocks():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] સ્કેનિંગ શરૂ થઈ રહ્યું છે...")
    
    tickers = get_stocks_from_sheet()
    if not tickers:
        print("શીટમાંથી કોઈ સ્ટોક મળ્યા નથી.")
        return

    # બધા સ્ટોક્સનો ડેટા એકસાથે ડાઉનલોડ (Zero Rate-limit issue)
    print(f"કુલ {len(tickers)} સ્ટોક્સનો ડેટા ડાઉનલોડ થઈ રહ્યો છે...")
    try:
        data = yf.download(tickers, period="3y", interval="1d", group_by='ticker', progress=False, threads=True)
    except Exception as e:
        print(f"Download Error: {e}")
        return

    results = []

    for ticker in tickers:
        try:
            # સિમ્બોલ મુજબ ડેટા મેળવવો
            if len(tickers) == 1:
                df = data.copy()
            else:
                if ticker not in data.columns.levels[0]:
                    continue
                df = data[ticker].copy()

            # સંપૂર્ણપણે ખાલી રો હટાવો
            df = df.dropna(subset=['Close', 'High', 'Low'])

            if len(df) < 20:
                continue

            cmp = float(df['Close'].iloc[-1])
            today_high = float(df['High'].iloc[-1])
            today_low = float(df['Low'].iloc[-1])

            if math.isnan(cmp) or cmp <= 0:
                continue

            cmp = round(cmp, 2)

            # પાછલા દિવસોના હાઈ (આજના દિવસ સિવાય)
            high_1m_prev = float(df['High'].iloc[-21:-1].max()) if len(df) >= 21 else float(df['High'].iloc[:-1].max())
            high_3m_prev = float(df['High'].iloc[-63:-1].max()) if len(df) >= 63 else float(df['High'].iloc[:-1].max())
            high_6m_prev = float(df['High'].iloc[-126:-1].max()) if len(df) >= 126 else float(df['High'].iloc[:-1].max())
            high_1y_prev = float(df['High'].iloc[-252:-1].max()) if len(df) >= 252 else float(df['High'].iloc[:-1].max())
            high_3y_prev = float(df['High'].iloc[:-1].max())

            # આજના દિવસ સહિતના હાઈ
            high_1m = float(df['High'].iloc[-21:].max()) if len(df) >= 21 else float(df['High'].max())
            high_3m = float(df['High'].iloc[-63:].max()) if len(df) >= 63 else float(df['High'].max())
            high_6m = float(df['High'].iloc[-126:].max()) if len(df) >= 126 else float(df['High'].max())
            high_1y = float(df['High'].iloc[-252:].max()) if len(df) >= 252 else float(df['High'].max())
            high_3y = float(df['High'].max())

            low_20d = float(df['Low'].iloc[-20:].min())
            low_52w = float(df['Low'].iloc[-252:].min()) if len(df) >= 252 else float(df['Low'].min())
            
            dist_1m = round(((high_1m - cmp) / cmp) * 100, 2)
            dist_3m = round(((high_3m - cmp) / cmp) * 100, 2)
            dist_6m = round(((high_6m - cmp) / cmp) * 100, 2)
            dist_1y = round(((high_1y - cmp) / cmp) * 100, 2)
            dist_3y = round(((high_3y - cmp) / cmp) * 100, 2)

            # કયા હાઈ તૂટ્યા
            highs_broken = []
            if today_high >= high_1m_prev:
                highs_broken.append("1M")
            if today_high >= high_3m_prev:
                highs_broken.append("3M")
            if today_high >= high_6m_prev:
                highs_broken.append("6M")
            if today_high >= high_1y_prev:
                highs_broken.append("1YR")
            if today_high >= high_3y_prev:
                highs_broken.append("3YR")
                
            broken_20d_low = today_low <= low_20d
            car_status = calculate_car_status(df['Close'])
            
            results.append({
                'Stock': ticker.replace('.NS', '').replace('.BO', ''),
                'CMP': cmp,
                'Dist_3Y': dist_3y, 'High_3Y': round(high_3y, 2),
                'Dist_1Y': dist_1y, 'High_1Y': round(high_1y, 2),
                'Dist_6M': dist_6m, 'High_6M': round(high_6m, 2),
                'Dist_3M': dist_3m, 'High_3M': round(high_3m, 2),
                'Dist_1M': dist_1m, 'High_1M': round(high_1m, 2),
                'Highs_Broken': " | ".join(highs_broken),
                'Broken_20d_Low': broken_20d_low,
                'CAR_Status': car_status,
                'Low_52w': round(low_52w, 2)
            })
        except Exception:
            continue
            
    df_res = pd.DataFrame(results)
    if df_res.empty:
        send_telegram_message("આજે કોઈ ડેટા મળ્યો નથી.")
        return

    used_stocks = set()
    final_msg = "📊 **માર્કેટનામા - ડાર્વાસ બોક્સ સ્કેનર** 📊\n\n"
    
    # ૧. નવો હાઈ લગાવનાર સ્ટોક્સ (ટેબલ ફોર્મેટ)
    df_highs = df_res[df_res['Highs_Broken'] != '']
    if not df_highs.empty:
        final_msg += "🚀 **આજે નવો હાઈ લગાવનાર સ્ટોક્સ:**\n"
        for _, row in df_highs.iterrows():
            final_msg += f"▪️ `{row['Stock']}` ₹{row['CMP']} | {row['Highs_Broken']} | CAR: *{row['CAR_Status']}*\n"
        final_msg += "\n"
    
    # ૨. NEAR HIGHS સેક્શન્સ
    df_3y = df_res.sort_values('Dist_3Y').head(3)
    final_msg += "🎯 **NEAR 3-YEAR HIGH (Top 3)**\n"
    for _, row in df_3y.iterrows():
        final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 3Y High: ₹{row['High_3Y']} ({row['Dist_3Y']}% દૂર) | CAR: *{row['CAR_Status']}*\n"
        used_stocks.add(row['Stock'])
        
    df_1y = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_1Y').head(3)
    final_msg += "\n🎯 **NEAR 1-YEAR HIGH (Top 3)**\n"
    for _, row in df_1y.iterrows():
        final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 1Y: ₹{row['High_1Y']} | 3Y(T): ₹{row['High_3Y']} ({row['Dist_1Y']}% દૂર) | CAR: *{row['CAR_Status']}*\n"
        used_stocks.add(row['Stock'])

    df_6m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_6M').head(3)
    final_msg += "\n🎯 **NEAR 6-MONTH HIGH (Top 3)**\n"
    for _, row in df_6m.iterrows():
        final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 6M: ₹{row['High_6M']} | 1Y(T): ₹{row['High_1Y']} ({row['Dist_6M']}% દૂર) | CAR: *{row['CAR_Status']}*\n"
        used_stocks.add(row['Stock'])

    df_3m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_3M').head(3)
    final_msg += "\n🎯 **NEAR 3-MONTH HIGH (Top 3)**\n"
    for _, row in df_3m.iterrows():
        final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 3M: ₹{row['High_3M']} | 6M(T): ₹{row['High_6M']} ({row['Dist_3M']}% દૂર) | CAR: *{row['CAR_Status']}*\n"
        used_stocks.add(row['Stock'])

    df_1m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_1M').head(3)
    final_msg += "\n🎯 **NEAR 1-MONTH HIGH (Top 3)**\n"
    for _, row in df_1m.iterrows():
        final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 1M: ₹{row['High_1M']} | 3M(T): ₹{row['High_3M']} ({row['Dist_1M']}% દૂર) | CAR: *{row['CAR_Status']}*\n"

    # ૩. ૨૦-દિવસનો લો તોડનારા
    df_lows = df_res[df_res['Broken_20d_Low'] == True].head(5)
    if not df_lows.empty:
        final_msg += "\n🩸 **20-દિવસનો લો તોડનારા (Bottom Fishing)**\n"
        for _, row in df_lows.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 52W Low: ₹{row['Low_52w']} | CAR: *{row['CAR_Status']}*\n"

    send_telegram_message(final_msg)
    print("રિપોર્ટ સફળતાપૂર્વક મોકલાઈ ગયો!")

if __name__ == "__main__":
    analyze_stocks()
