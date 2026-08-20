import pandas as pd
import yfinance as yf
import requests
import warnings
import time
from datetime import datetime

warnings.filterwarnings('ignore')

# ============================================================
# ૧. ક્રેડેન્શિયલ્સ & Google Sheets URL
# ============================================================
TELEGRAM_BOT_TOKEN = '8896031421:AAFIeqDTKsH64aAnaCuiuW8F9aZxMTIEA9g'
TELEGRAM_CHAT_ID = '1051774043'

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1eKumGC4e2MV1jPjoG3LvOtvJ24SKUz2Y5YPkO5WUPlQ/export?format=csv'

def send_telegram_message(message):
    """ટેલિગ્રામ મેસેજ મોકલવા માટેનું ફંક્શન"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_stocks_from_sheet():
    """ગૂગલ શીટમાંથી સ્ટોક્સની લિસ્ટ લાવે છે"""
    try:
        df = pd.read_csv(SHEET_URL + '&t=' + str(datetime.now().timestamp()))
        stocks = df.iloc[:, 0].dropna().tolist()
        return [str(s).strip() for s in stocks if str(s).strip() != '']
    except Exception as e:
        print(f"ગૂગલ શીટ વાંચવામાં એરર: {e}")
        return []

# ============================================================
# ૨. સાંજનો માર્કેટનામા - ડાર્વાસ બોક્સ રિપોર્ટ (તમારો ઓરિજિનલ કોડ)
# ============================================================
def analyze_stocks_eod():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] સાંજનો Darvas Box રિપોર્ટ તૈયાર થઈ રહ્યો છે...")
    
    tickers = get_stocks_from_sheet()
    if not tickers:
        print("શીટમાંથી કોઈ સ્ટોક મળ્યા નથી.")
        return

    results = []
    
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="3y", interval="1d", progress=False)
                
            if df.empty or len(df) < 20:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
                
            cmp = round(float(df['Close'].iloc[-1]), 2)
            today_high = float(df['High'].iloc[-1])
            today_low = float(df['Low'].iloc[-1])
            
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
            
            results.append({
                'Stock': ticker.replace('.NS', '').replace('.BO', ''),
                'CMP': cmp,
                'Dist_3Y': dist_3y, 'High_3Y': round(high_3y, 2),
                'Dist_1Y': dist_1y, 'High_1Y': round(high_1y, 2),
                'Dist_6M': dist_6m, 'High_6M': round(high_6m, 2),
                'Dist_3M': dist_3m, 'High_3M': round(high_3m, 2),
                'Dist_1M': dist_1m, 'High_1M': round(high_1m, 2),
                'New_High': new_high,
                'Broken_20d_Low': broken_20d_low,
                'Low_20d': round(low_20d, 2),
                'Low_52w': round(low_52w, 2)
            })
        except Exception:
            continue
            
    df_res = pd.DataFrame(results)
    if df_res.empty:
        send_telegram_message("આજે કોઈ ડેટા મળ્યો નથી (બધા સ્ટોક્સનું સ્કેનિંગ નિષ્ફળ).")
        return

    used_stocks = set()
    final_msg = "📊 **માર્કેટનામા - ડાર્વાસ બોક્સ સ્કેનર** 📊\n\n"
    
    new_highs = df_res[df_res['New_High'] == True]['Stock'].tolist()
    if new_highs:
        final_msg += "🚀 **આજે નવો હાઈ લગાવનાર સ્ટોક્સ:**\n" + ", ".join(new_highs) + "\n\n"
    
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
    print("સાંજનો રિપોર્ટ સફળતાપૂર્વક મોકલાઈ ગયો.")

# ============================================================
# ૩. લાઈવ VCP / Pivot Breakout સ્કેનર
# ============================================================
triggered_today = set()

def monitor_live_breakouts():
    """ગૂગલ શીટના સ્ટોક્સમાં લાઈવ બ્રેકઆઉટ ચકાસે છે"""
    tickers = get_stocks_from_sheet()
    if not tickers:
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] લાઈવ બ્રેકઆઉટ સ્કેનિંગ ચાલુ છે ({len(tickers)} સ્ટોક્સ)...")

    for ticker in tickers:
        if ticker in triggered_today:
            continue

        try:
            df_intraday = yf.download(ticker, period="5d", interval="5m", progress=False)
            df_daily = yf.download(ticker, period="60d", interval="1d", progress=False)

            if df_intraday.empty or df_daily.empty or len(df_daily) < 21:
                continue

            if isinstance(df_intraday.columns, pd.MultiIndex):
                df_intraday.columns = df_intraday.columns.droplevel(1)
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily.columns = df_daily.columns.droplevel(1)

            # પાછલા ૨૦ દિવસનો હાઈ (Pivot High)
            pivot_price = float(df_daily['High'].iloc[-21:-1].max())
            
            latest_price = float(df_intraday['Close'].iloc[-1])
            current_vol = float(df_intraday['Volume'].iloc[-1])
            avg_vol = float(df_intraday['Volume'].tail(30).mean())

            # બ્રેકઆઉટ શરતો: Pivot High તોડ્યો + 1.5x વોલ્યુમ સર્જ
            if latest_price > pivot_price and current_vol > (avg_vol * 1.5):
                stock_name = ticker.replace('.NS', '').replace('.BO', '')
                vol_surge = round(current_vol / avg_vol, 1) if avg_vol > 0 else 1.0
                
                msg = (
                    f"🚀 *LIVE PIVOT BREAKOUT ALERT!* 🚀\n\n"
                    f"📌 *Stock:* `{stock_name}`\n"
                    f"💰 *CMP:* ₹{latest_price:.2f}\n"
                    f"🎯 *Pivot (20D High):* ₹{pivot_price:.2f}\n"
                    f"📊 *Volume Surge:* {vol_surge}x (5-Min Avg)\n"
                    f"⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}\n"
                    f"💡 *Action:* VCP / Darvas Box માંથી બ્રેકઆઉટ!"
                )
                send_telegram_message(msg)
                triggered_today.add(ticker)
                print(f"બ્રેકઆઉટ એલર્ટ મોકલાયો: {stock_name}")
                
        except Exception:
            continue

# ============================================================
# ૪. મુખ્ય લાઈવ લૂપ (Main Loop)
# ============================================================
if __name__ == "__main__":
    test_current_breakouts_now()
    
    send_telegram_message("🤖 *બોટ સક્રિય થયો છે!*\nલાઈવ બ્રેકઆઉટ અને સાંજનો રિપોર્ટ બંને ચાલુ છે.")
    
    eod_report_sent = False

    while True:
        now = datetime.now()
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        eod_time = now.replace(hour=15, minute=35, second=0)

        # ૧. સપ્તાહાંત (શનિ-રવિ)
        if now.weekday() >= 5:
            print("વીકેન્ડ (શનિ/રવિ) છે. બોટ સ્લીપ મોડમાં છે...")
            time.sleep(3600)
            continue

        # ૨. માર્કેટ અવર્સ (૦૯:૧૫ થી ૧૫:૩૦) -> લાઈવ સ્કેનિંગ દર ૩ મિનિટે
        if market_open <= now <= market_close:
            monitor_live_breakouts()
            time.sleep(180)

        # ૩. માર્કેટ બંધ થયા પછી (૧૫:૩૫ વાગ્યે) -> સાંજનો ડાર્વાસ બોક્સ રિપોર્ટ
        elif now >= eod_time and not eod_report_sent:
            analyze_stocks_eod()
            eod_report_sent = True
            time.sleep(60)

        # ૪. રાત્રે ૭:૦૦ વાગ્યે -> બીજા દિવસ માટે રીસેટ
        elif now.hour >= 19:
            triggered_today.clear()
            eod_report_sent = False
            time.sleep(3600)

        # બાકીના સમયમાં રાહ જુઓ
        else:
            time.sleep(300)
