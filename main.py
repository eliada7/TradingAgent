import os
import io
import asyncio
import httpx
import yfinance as yf
import pandas_ta as ta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
from fastapi import FastAPI
from contextlib import asynccontextmanager

# المفاتيح والمعلومات الرئيسية
TELEGRAM_BOT_TOKEN = "8736155366:AAGy8375LQ-myDoXi6BAmN-xtr1jSs5rFlA"

# مفتاح Gemini API (يمكن وضعه هنا أو ضبه كـ Environment Variable)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# قائمة الأسهم المتابعة
SYMBOLS = ["SST", "MTEN", "CPSH", "MVIS", "WGS", "NVDA", "AAPL"]

async def send_telegram_photo_with_caption(caption: str, photo_bytes: bytes, chat_id: str = None):
    """إرسال صورة الشارت مع تقرير التليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    if not chat_id:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates")
                updates = res.json()
                if updates.get("result"):
                    chat_id = updates["result"][-1]["message"]["chat"]["id"]
                else:
                    return
        except Exception as e:
            print(f"خطأ في جلب Chat ID: {e}")
            return

    files = {'photo': ('chart.png', photo_bytes, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(url, data=data, files=files)

async def analyze_with_gemini(symbol: str, price: float, rsi: float, macd_signal: str, trend: str) -> str:
    """استدعاء Gemini AI لتقديم تحليل فني ومالي ذكي للموقف"""
    if not GEMINI_API_KEY:
        return "💡 _تنبيه فني مباشر بدون تحليل الذكاء الاصطناعي (يرجى إضافة GEMINI_API_KEY لتفعيله)._"
    
    prompt = f"""
    أنت خبير تداول ووكيل تحليل مالي بالذكاء الاصطناعي.
    قم بتقديم تحليل مختصر وجذاب لسهم {symbol} بناءً على البيانات الفنية اللحظية التالية:
    - السعر الحالي: ${price}
    - مؤشر RSI (14): {rsi}
    - تقاطع مؤشر MACD: {macd_signal}
    - الاتجاه العام (EMA 20/50): {trend}

    المطلوب:
    1. تقييم سريع للفرصة في 2-3 أسطر باللغة العربية.
    2. نصيحة حول التعامل مع إدارة المخاطر (مثل وقف الخسارة الإسترشادي أو الهدف).
    اجعل النبرة احترافية ومشجعة ومباشرة وتليق بتنبهات التليجرام.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            analysis_text = result['candidates'][0]['content']['parts'][0]['text']
            return f"🤖 **تحليل الذكاء الاصطناعي (Gemini):**\n{analysis_text}"
    except Exception as e:
        print(f"خطأ في استدعاء Gemini: {e}")
        return "💡 _تحليل فني بناءً على المؤشرات الفنية الرقمية._"

def generate_chart_image(df, symbol):
    """رسم الشارت بالشموع اليابانية + المتوسطات + الـ RSI"""
    df_chart = df.tail(40).copy()
    
    # إضافة المؤشرات للشارت
    plots = [
        mpf.make_addplot(df_chart['EMA_20'], color='blue', width=1),
        mpf.make_addplot(df_chart['EMA_50'], color='orange', width=1),
        mpf.make_addplot(df_chart['RSI'], panel=1, color='purple', ylabel='RSI')
    ]
    
    buf = io.BytesIO()
    mpf.plot(
        df_chart,
        type='candle',
        style='charles',
        title=f"\nChart: {symbol} (EMA20: Blue, EMA50: Orange)",
        addplot=plots,
        figsize=(8, 6)
    )
    buf.seek(0)
    return buf.getvalue()

async def check_market_signals():
    """المحرك الرئيسي للفحص الدوري والتحليل الفني والذكاء الاصطناعي"""
    while True:
        try:
            for symbol in SYMBOLS:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval="5m")
                
                if not df.empty and len(df) > 50:
                    # حساب المؤشرات الفنية
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    
                    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
                    df['MACD'] = macd['MACD_12_26_9']
                    df['MACDs'] = macd['MACDs_12_26_9']
                    
                    df['EMA_20'] = ta.ema(df['Close'], length=20)
                    df['EMA_50'] = ta.ema(df['Close'], length=50)
                    
                    latest_price = round(df['Close'].iloc[-1], 2)
                    latest_rsi = round(df['RSI'].iloc[-1], 2)
                    latest_macd = df['MACD'].iloc[-1]
                    latest_macds = df['MACDs'].iloc[-1]
                    prev_macd = df['MACD'].iloc[-2]
                    prev_macds = df['MACDs'].iloc[-2]
                    
                    # تحديد حالة الاتجاه والتقاطع
                    trend = "صاعد 📈" if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] else "هابط 📉"
                    
                    macd_signal = "عادي"
                    if prev_macd < prev_macds and latest_macd > latest_macds:
                        macd_signal = "تقاطع إيجابي صاعد (Bullish Cross)"
                    elif prev_macd > prev_macds and latest_macd < latest_macds:
                        macd_signal = "تقاطع سلبي هابط (Bearish Cross)"
                    
                    signal = None
                    # شرط الشراء المتقدم: RSI تحت 35 + اتجاه صاعد أو تقاطع إيجابي
                    if latest_rsi < 35 or macd_signal == "تقاطع إيجابي صاعد (Bullish Cross)":
                        signal = "🟢 **فرصة شراء (BUY)**"
                    elif latest_rsi > 70 or macd_signal == "تقاطع سلبي هابط (Bearish Cross)":
                        signal = "🔴 **فرصة بيع (SELL)**"
                    
                    if signal:
                        # 1. تحليل الذكاء الاصطناعي Gemini
                        ai_report = await analyze_with_gemini(symbol, latest_price, latest_rsi, macd_signal, trend)
                        
                        # 2. توليد صورة الشارت
                        chart_bytes = generate_chart_image(df, symbol)
                        
                        caption = (
                            f"🚀 **تنبيه وكيل التداول الذكي (Trading Agent)**\n\n"
                            f"📌 **السهم:** `{symbol}`\n"
                            f"💵 **السعر:** `${latest_price}`\n"
                            f"📊 **مؤشر RSI:** `{latest_rsi}`\n"
                            f"🌊 **الزخم (MACD):** {macd_signal}\n"
                            f"📐 **الاتجاه العام:** {trend}\n"
                            f"🎯 **الإشارة:** {signal}\n\n"
                            f"{ai_report}\n\n"
                            f"🔗 [افتح الشارت التفاعلي على TradingView](https://www.tradingview.com/chart/?symbol={symbol})"
                        )
                        await send_telegram_photo_with_caption(caption, chart_bytes)
                        
        except Exception as e:
            print(f"خطأ أثناء الفحص الفني: {e}")
            
        # فحص كل 5 دقائق
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(check_market_signals())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Full AI Trading Agent is active 24/7!"}
