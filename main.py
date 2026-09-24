import os
import asyncio
import httpx
import yfinance as yf
import pandas_ta as ta
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager

TELEGRAM_BOT_TOKEN = "8736155366:AAGy8375LQ-myDoXi6BAmN-xtr1jSs5rFlA"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"  # أرسل أي رسالة للبوت وسيأخذ الـ Chat ID تلقائياً، أو سنحدده تلقائياً

# قائمة الأسهم المراد متابعتها
SYMBOLS = ["SST", "NVDA", "AAPL"]

async def send_telegram_message(message: str, chat_id: str = None):
    """إرسال رسالة إلى التليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # إذا لم يحدد chat_id، نسحب آخر chat_id تفاعل مع البوت
    if not chat_id:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates")
                updates = res.json()
                if updates.get("result"):
                    chat_id = updates["result"][-1]["message"]["chat"]["id"]
                else:
                    print("لم يتم العثور على Chat ID، يرجى إرسال أي رسالة للبوت أولاً.")
                    return
        except Exception as e:
            print(f"خطأ في جلب Chat ID: {e}")
            return

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def check_market_signals():
    """مهمة تعمل في الخلفية لفحص الأسهم بشكل دوري"""
    while True:
        try:
            for symbol in SYMBOLS:
                # سحب بيانات السهم (آخر يومين بفريم 5 دقائق)
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="2d", interval="5m")
                
                if not df.empty and len(df) > 14:
                    # حساب مؤشر RSI
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    
                    latest_price = round(df['Close'].iloc[-1], 2)
                    latest_rsi = round(df['RSI'].iloc[-1], 2)
                    
                    signal = None
                    if latest_rsi < 35:
                        signal = "🟢 فرصة شراء (BUY) - تشبع بيعي!"
                    elif latest_rsi > 70:
                        signal = "🔴 فرصة بيع (SELL) - تشبع شرائي!"
                    
                    # إذا تحققت إشارة، يتم إرسال التنبيه فوراً
                    if signal:
                        msg = (
                            f"📊 **تنبيه آلي مستقل**\n\n"
                            f"🔹 **السهم:** `{symbol}`\n"
                            f"💵 **السعر الحالي:** `${latest_price}`\n"
                            f"📈 **مؤشر RSI:** `{latest_rsi}`\n"
                            f"🎯 **الإشارة:** {signal}\n\n"
                            f"⚡ _تم الفحص تلقائياً من سيرفرك الخاص._"
                        )
                        await send_telegram_message(msg)
                        
        except Exception as e:
            print(f"خطأ أثناء فحص السوق: {e}")
            
        # الانتظار 300 ثانية (5 دقائق) قبل الفحص القادم
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # تشغيل الفحص الدوري عند بدء السيرفر
    task = asyncio.create_task(check_market_signals())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Trading Agent is running successfully 24/7!"}

@app.post("/webhook")
async def webhook(data: dict):
    # إمكانية استقبال أي تنبيه خارجي أيضاً
    ticker = data.get("ticker", "N/A")
    price = data.get("price", "N/A")
    rsi = data.get("rsi", "N/A")
    action = data.get("action", "BUY")
    
    msg = (
        f"🚨 **تنبيه خاص** 🚨\n\n"
        f"📌 **السهم:** `{ticker}`\n"
        f"💰 **السعر:** `${price}`\n"
        f"📊 **RSI:** `{rsi}`\n"
        f"🎬 **الإجراء:** `{action}`"
    )
    await send_telegram_message(msg)
    return {"status": "success"}
