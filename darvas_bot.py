import pandas as pd
import yfinance as yf
import requests
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# ============================================================
# ૧. ક્રેડેન્શિયલ્સ & Google Sheet URL
# ============================================================
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
        print(f"Sheet error: {e}")
        return []

# ============================================================
# ૨. મુખ્ય કમ્બાઈન્ડ સ્કેનર (Darvas Box + Minervini)
# ============================================================
def run_full_market_scan():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] સ્કેનિંગ શરૂ થઈ રહ્યું છે...")
    tickers = get_stocks_from_sheet()
    
    if not tickers:
        print("શીટમાંથી કોઈ સ્ટોક મળ્યા નથી.")
        return

    darvas_results = []
    minervini_stocks = []
    pivot_breakouts = []

    for ticker in tickers:
        try:
            df = yf.download(ticker, period="3y", interval="1d", progress=False)
            
            if df.empty:
                continue

            # MultiIndex કોલમ હેન્ડલિંગ & NaN ક્લીનિંગ
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()

            if len(df) < 20:
                continue

            stock_name = ticker.replace('.NS', '').replace('.BO', '')
            cmp = round(float(df['Close'].iloc[-1]), 2)
            today_high = float(df['High'].iloc[-1])
            today_low = float(df['Low'].iloc[-1])

            # ----------------------------------------------------
            # A. Darvas Box High/Low કેલ્ક્યુલેશન
            # ----------------------------------------------------
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

            new_high = today_high >= high_1m
            broken_20d_low = today_low <= low_20d

            darvas_results.append({
                'Stock': stock_name,
                'CMP': cmp,
                'Dist_3Y': dist_3y, 'High_3Y': round(high_3y, 2),
                'Dist_1Y': dist_1y, 'High_1Y': round(high_1y, 2),
                'Dist_6M': dist_6m, 'High_6M': round(high_6m, 2),
                'Dist_3M': dist_3m, 'High_3M': round(high_3m, 2),
                'Dist_1M': dist_1m, 'High_1M': round(high_1m, 2),
                'New_High': new_high,
                'Broken_20d_Low': broken_20d_low,
                'Low_52w': round(low_52w, 2)
            })

            # ----------------------------------------------------
            # B. Minervini Trend Template & Pivot Breakout
            # ----------------------------------------------------
            if len(df) >= 200:
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA150'] = df['Close'].rolling(150).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()

                sma50 = float(df['SMA50'].iloc[-1])
                sma150 = float(df['SMA150'].iloc[-1])
                sma200 = float(df['SMA200'].iloc[-1])
                sma200_prev = float(df['SMA200'].iloc[-22])

                # Minervini શરતો
                c1 = cmp > sma150 and cmp > sma200
                c2 = sma150 > sma200
                c3 = sma200 > sma200_prev
                c4 = sma50 > sma150 and sma50 > sma200
                c5 = cmp > sma50
                c6 = cmp > (low_52w * 1.25)
                c7 = cmp > (high_1y * 0.75)

                if c1 and c2 and c3 and c4 and c5 and c6 and c7:
                    range_10d = (df['High'].iloc[-10:].max() - df['Low'].iloc[-10:].min()) / df['Low'].iloc[-10:].min() * 100
                    vol_sma50 = df['Volume'].rolling(50).mean().iloc[-1]
                    vol_recent = df['Volume'].iloc[-5:].mean()
                    is_dry = vol_recent < vol_sma50

                    minervini_stocks.append({
                        'Stock': stock_name,
                        'CMP': cmp,
                        'Dist_High': dist_1y,
                        'Tightness': round(range_10d, 1),
                        'Dry_Up': "હા" if is_dry else "ના"
                    })

                # Pivot Breakout Check
                pivot_price = float(df['High'].iloc[-21:-1].max())
                vol_today = float(df['Volume'].iloc[-1])
                vol_avg20 = float(df['Volume'].iloc[-21:-1].mean())
                vol_surge = round(vol_today / vol_avg20, 1) if vol_avg20 > 0 else 1.0

                if today_high >= pivot_price and vol_surge >= 1.2:
                    pivot_breakouts.append({
                        'Stock': stock_name,
                        'CMP': cmp,
                        'Pivot': round(pivot_price, 2),
                        'Vol': vol_surge
                    })

        except Exception:
            continue

    # ============================================================
    # ૩. ટેલિગ્રામ મેસેજ બનાવવો
    # ============================================================
    final_msg = ""

    # વિભાગ ૧: Minervini & Pivot Breakouts (નવું સેટઅપ)
    if pivot_breakouts or minervini_stocks:
        final_msg += "🏆 **MINERVINI & PIVOT BREAKOUTS** 🏆\n\n"
        
        if pivot_breakouts:
            final_msg += "🚀 **આજના PIVOT BREAKOUTS (High Vol):**\n"
            for s in pivot_breakouts[:5]:
                final_msg += f"▪️ {s['Stock']}: CMP ₹{s['CMP']} | Pivot: ₹{s['Pivot']} (Vol: {s['Vol']}x)\n"
            final_msg += "\n"

        if minervini_stocks:
            df_mine = pd.DataFrame(minervini_stocks).sort_values('Dist_High').head(5)
            final_msg += "🎯 **TOP MINERVINI TREND TEMPLATE:**\n"
            for _, row in df_mine.iterrows():
                final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 52W High થી {row['Dist_High']}% દૂર (Vol Dry: {row['Dry_Up']})\n"
            final_msg += "\n" + "—"*18 + "\n\n"

    # વિભાગ ૨: માર્કેટનામા - ડાર્વાસ બોક્સ સ્કેનર (તમારો ઓરિજિનલ રિપોર્ટ)
    df_res = pd.DataFrame(darvas_results)
    if not df_res.empty:
        final_msg += "📊 **માર્કેટનામા - ડાર્વાસ બોક્સ સ્કેનર** 📊\n\n"

        new_highs = df_res[df_res['New_High'] == True]['Stock'].tolist()
        if new_highs:
            final_msg += "🚀 **આજે નવો હાઈ લગાવનાર સ્ટોક્સ:**\n" + ", ".join(new_highs) + "\n\n"

        used_stocks = set()

        df_3y = df_res.sort_values('Dist_3Y').head(3)
        final_msg += "🎯 **NEAR 3-YEAR HIGH (Top 3)**\n"
        for _, row in df_3y.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 3Y High: ₹{row['High_3Y']} ({row['Dist_3Y']}% દૂર)\n"
            used_stocks.add(row['Stock'])

        df_1y = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_1Y').head(3)
        final_msg += "\n🎯 **NEAR 1-YEAR HIGH (Top 3)**\n"
        for _, row in df_1y.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 1Y: ₹{row['High_1Y']} | 3Y(T): ₹{row['High_3Y']} ({row['Dist_1Y']}% દૂર)\n"
            used_stocks.add(row['Stock'])

        df_6m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_6M').head(3)
        final_msg += "\n🎯 **NEAR 6-MONTH HIGH (Top 3)**\n"
        for _, row in df_6m.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 6M: ₹{row['High_6M']} | 1Y(T): ₹{row['High_1Y']} ({row['Dist_6M']}% દૂર)\n"
            used_stocks.add(row['Stock'])

        df_3m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_3M').head(3)
        final_msg += "\n🎯 **NEAR 3-MONTH HIGH (Top 3)**\n"
        for _, row in df_3m.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 3M: ₹{row['High_3M']} | 6M(T): ₹{row['High_6M']} ({row['Dist_3M']}% દૂર)\n"
            used_stocks.add(row['Stock'])

        df_1m = df_res[~df_res['Stock'].isin(used_stocks)].sort_values('Dist_1M').head(3)
        final_msg += "\n🎯 **NEAR 1-MONTH HIGH (Top 3)**\n"
        for _, row in df_1m.iterrows():
            final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 1M: ₹{row['High_1M']} | 3M(T): ₹{row['High_3M']} ({row['Dist_1M']}% દૂર)\n"

        df_lows = df_res[df_res['Broken_20d_Low'] == True].head(5)
        if not df_lows.empty:
            final_msg += "\n🩸 **20-દિવસનો લો તોડનારા (Bottom Fishing)**\n"
            for _, row in df_lows.iterrows():
                final_msg += f"▪️ {row['Stock']}: CMP ₹{row['CMP']} | 52W Low: ₹{row['Low_52w']}\n"

    send_telegram_message(final_msg)
    print("કમ્પ્લીટ રિપોર્ટ ટેલિગ્રામ પર મોકલાઈ ગયો!")

# ============================================================
# રન કરો
# ============================================================
if __name__ == "__main__":
    run_full_market_scan()
