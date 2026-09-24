import os
import io
import asyncio
import httpx
import yfinance as yf
import pandas_ta as ta
import matplotlib
matplotlib.use('Agg') # لمنع فتح نوافذ على السيرفر
import matplotlib.pyplot as plt
import mplfinance as mpf
from fastapi import FastAPI
from contextlib import asynccontextmanager

TELEGRAM_BOT_TOKEN = "8736155366:AAGy8375LQ-myDoXi6BAmN-xtr1jSs5rFlA"
SYMBOLS = ["SST", "MTEN", "CPSH", "MVIS", "WGS"]

async def send_telegram_photo_with_caption(caption: str, photo_bytes: bytes, chat_id: str = None):
    """إرسال صورة الشارت مع النص للتليجرام"""
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
    
    async with httpx.AsyncClient() as client:
        await client.post(url, data=data, files=files)

def generate_chart_image(df, symbol):
    """رسم الشارت بأسلوب الشموع اليابانية مع الـ RSI في الذاكرة"""
    df_chart = df.tail(40).copy() # آخر 40 شمعة
    
    # إعدادات رسم الـ RSI والشموع
    rsi_plot = mpf.make_addplot(df_chart['RSI'], panel=1, color='purple', ylabel='RSI')
    
    buf = io.BytesIO()
    mpf.plot(
        df_chart,
        type='candle',
        style='charles',
        title=f"\nChart: {symbol}",
        volume=False,
        addplot=rsi_plot,
        savefig=buf,
        figsize=(8, 6)
    )
    buf.seek(0)
    return buf.getvalue()

async def check_market_signals():
    """مهمة فحص الأسهم وإرسال التنبيهات مع الشارت"""
    while True:
        try:
            for symbol in SYMBOLS:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="2d", interval="5m")
                
                if not df.empty and len(df) > 14:
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    
                    latest_price = round(df['Close'].iloc[-1], 2)
                    latest_rsi = round(df['RSI'].iloc[-1], 2)
                    
                    signal = None
                    if latest_rsi < 35:
                        signal = "🟢 **فرصة شراء (BUY)** - تشبع بيعي!"
                    elif latest_rsi > 70:
                        signal = "🔴 **فرصة بيع (SELL)** - تشبع شرائي!"
                    
                    if signal:
                        # إنشاء صورة الشارت
                        chart_bytes = generate_chart_image(df, symbol)
                        
                        caption = (
                            f"📈 **تنبيه تحليل فني وشارت آلي** 📉\n\n"
                            f"🔹 **السهم:** `{symbol}`\n"
                            f"💵 **السعر الحالي:** `${latest_price}`\n"
                            f"📊 **مؤشر RSI:** `{latest_rsi}`\n"
                            f"🎯 **الإشارة:** {signal}\n\n"
                            f"🔗 [افتح الشارت التفاعلي على TradingView](https://www.tradingview.com/chart/?symbol={symbol})\n\n"
                            f"⚡ _مرفق الشارت اللحظي المحدث._"
                        )
                        await send_telegram_photo_with_caption(caption, chart_bytes)
                        
        except Exception as e:
            print(f"خطأ أثناء رسم الشارت أو الفحص: {e}")
            
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(check_market_signals())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Trading Agent with Charts is running successfully 24/7!"}
