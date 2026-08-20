import pandas as pd
import yfinance as yf
import requests
import warnings
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
        return [str(s).strip() for s in stocks if str(s).strip() != '']
    except Exception as e:
        print(f"ગૂગલ શીટ વાંચવામાં એરર: {e}")
        return []

def calculate_car_status(df):
    """
    Cumulative Average Reversal (CAR) સ્ટેટસ ગણતરી:
    - 200 SMA ઉપલબ્ધ ન હોય તો -> SHORT HISTORY
    - CMP > 50 SMA અને CMP > 200 SMA અને 200 SMA વધતી હોય -> BUY / AVERAGE
    - બાકી -> AVOID
    """
    if len(df) < 200:
        return "SHORT HISTORY"
    
    df_calc = df.copy()
    df_calc['SMA50'] = df_calc['Close'].rolling(50).mean()
    df_calc['SMA200'] = df_calc['Close'].rolling(200).mean()

    cmp = float(df_calc['Close'].iloc[-1])
    sma50 = float(df_calc['SMA50'].iloc[-1])
    sma200 = float(df_calc['SMA200'].iloc[-1])
    prev_sma200 = float(df_calc['SMA200'].iloc[-20])

    if cmp > sma50 and cmp > sma200 and sma200 >= prev_sma200:
        return "BUY / AVERAGE"
    else:
        return "AVOID"

def analyze_stocks():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] સ્કેનિંગ શરૂ થઈ રહ્યું છે. કૃપા કરીને રાહ જુઓ...")
    
    tickers = get_stocks_from_sheet()
    if not tickers:
        print("શીટમાંથી કોઈ સ્ટોક મળ્યા નથી.")
        return

    print(f"કુલ {len(tickers)} સ્ટોક્સનું એક-પછી-એક સ્કેનિંગ ચાલુ છે...")
    
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
            
            # વિવિધ ટાઈમફ્રેમ્સના પાછલા હાઈ (આજના દિવસ સિવાય)
            high_1m_prev = float(df['High'].iloc[-21:-1].max()) if len(df) >= 21 else float(df['High'].iloc[:-1].max())
            high_3m_prev = float(df['High'].iloc[-63:-1].max()) if len(df) >= 63 else float(df['High'].iloc[:-1].max())
            high_6m_prev = float(df['High'].iloc[-126:-1].max()) if len(df) >= 126 else float(df['High'].iloc[:-1].max())
            high_1y_prev = float(df['High'].iloc[-252:-1].max()) if len(df) >= 252 else float(df['High'].iloc[:-1].max())
            high_3y_prev = float(df['High'].iloc[:-1].max())
            
            # આજના દિવસ સહિતના હાઈ (Near Highs ગણતરી માટે)
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
            
            # કયા કયા હાઈ તૂટ્યા તે ચેક કરવું
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
            car_status = calculate_car_status(df)
            
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
    
    # ૧. નવો હાઈ લગાવનાર સ્ટોક્સનું ફોર્મેટેડ લિસ્ટ
    df_highs = df_res[df_res['Highs_Broken'] != '']
    if not df_highs.empty:
        final_msg += "🚀 **આજે નવો હાઈ લગાવનાર સ્ટોક્સ:**\n"
        for _, row in df_highs.iterrows():
            final_msg += f"▪️ `{row['Stock']}` ₹{row['CMP']} | {row['Highs_Broken']} | CAR: *{row['CAR_Status']}*\n"
        final_msg += "\n"
    
    # ૨. NEAR HIGHS સેક્શન્સ (CAR સ્ટેટસ સાથે)
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
    print("સ્કેનિંગ પૂર્ણ. ટેલિગ્રામ પર રિપોર્ટ મોકલી દેવામાં આવ્યો છે.")

if __name__ == "__main__":
    analyze_stocks()
