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
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

# بيانات التليجرام والمفاتيح
TELEGRAM_BOT_TOKEN = "8736155366:AAGy8375LQ-myDoXi6BAmN-xtr1jSs5rFlA"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# قائمة الأسهم المتابعة
SYMBOLS = ["SST", "MTEN", "CPSH", "MVIS", "WGS", "NVDA", "AAPL"]

async def send_telegram_message(text: str, chat_id: str):
    """إرسال رسالة نصية للتليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        await client.post(url, json=payload)

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

async def ask_gemini(prompt: str) -> str:
    """استدعاء ذكي لـ Gemini API يتنقل بين النماذج تلقائياً لتفادي أي أخطاء"""
    if not GEMINI_API_KEY:
        return "⚠️ مفتاح `GEMINI_API_KEY` غير مفعّل في السيرفر."
    
    clean_key = GEMINI_API_KEY.strip()
    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    print(f"نموذج {model} أرجع رمز الاستجابة: {response.status_code}")
            except Exception as e:
                print(f"خطأ أثناء الاتصال بـ {model}: {e}")
                
    return "عذراً، تعذر معالجة الطلب عبر الذكاء الاصطناعي حالياً. يرجى التأكد من صلاحية المفتاح أو المحاولة لاحقاً."

def get_stock_data_summary(symbol: str) -> str:
    """جلب ملخص فني سريع لأي سهم يطلبه المستخدم"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m")
        if df.empty or len(df) < 20:
            return f"تعذر جلب بيانات السهم `{symbol}`، تأكد من صحة الرمز."
        
        df['RSI'] = ta.rsi(df['Close'], length=14)
        latest_price = round(df['Close'].iloc[-1], 2)
        latest_rsi = round(df['RSI'].iloc[-1], 2)
        
        return f"بيانات فنية لحظية لسهم {symbol}:\n- السعر الحالي: ${latest_price}\n- مؤشر RSI: {latest_rsi}"
    except Exception as e:
        return f"خطأ في قراءة بيانات السهم: {e}"

def generate_chart_image(df, symbol):
    """رسم الشارت بالشموع اليابانية مع المتوسطات والمؤشرات"""
    df_chart = df.tail(40).copy()
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
        title=f"\nChart: {symbol}",
        addplot=plots,
        figsize=(8, 6)
    )
    buf.seek(0)
    return buf.getvalue()

async def check_market_signals():
    """مهمة الخلفية الدورية لمراقبة السوق"""
    while True:
        try:
            for symbol in SYMBOLS:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval="5m")
                
                if not df.empty and len(df) > 50:
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
                    
                    trend = "صاعد 📈" if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] else "هابط 📉"
                    macd_signal = "عادي"
                    if prev_macd < prev_macds and latest_macd > latest_macds:
                        macd_signal = "تقاطع إيجابي صاعد"
                    elif prev_macd > prev_macds and latest_macd < latest_macds:
                        macd_signal = "تقاطع سلبي هابط"
                    
                    signal = None
                    if latest_rsi < 35 or macd_signal == "تقاطع إيجابي صاعد":
                        signal = "🟢 **فرصة شراء (BUY)**"
                    elif latest_rsi > 70 or macd_signal == "تقاطع سلبي هابط":
                        signal = "🔴 **فرصة بيع (SELL)**"
                    
                    if signal:
                        prompt = f"قم بتقديم تحليل مالي وتوصية مختصرة جداً باللغة العربية لسهم {symbol}. السعر: ${latest_price}، RSI: {latest_rsi}، الاتجاه: {trend}."
                        ai_report = await ask_gemini(prompt)
                        chart_bytes = generate_chart_image(df, symbol)
                        
                        caption = (
                            f"🚀 **تنبيه آلي**\n\n"
                            f"📌 **السهم:** `{symbol}`\n"
                            f"💵 **السعر:** `${latest_price}`\n"
                            f"📊 **RSI:** `{latest_rsi}`\n"
                            f"🎯 **الإشارة:** {signal}\n\n"
                            f"🤖 **التحليل الذكي:**\n{ai_report}"
                        )
                        await send_telegram_photo_with_caption(caption, chart_bytes)
                        
        except Exception as e:
            print(f"خطأ في الفحص الدوري: {e}")
            
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ربط التليجرام بالـ Webhook الخاص بالسيرفر
    webhook_url = "https://eliada-trading-agent.onrender.com/telegram-webhook"
    async with httpx.AsyncClient() as client:
        await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}")
    
    task = asyncio.create_task(check_market_signals())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Full Interactive Trading Agent is active!"}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """استقبال رسائل المستخدم من تليجرام والرد عليها تفاعلياً عبر الذكاء الاصطناعي"""
    try:
        data = await request.json()
        if "message" in data and "text" in data["message"]:
            chat_id = str(data["message"]["chat"]["id"])
            user_text = data["message"]["text"].strip()
            
            # فحص إذا كانت الرسالة تحتوي على رمز سهم معين
            words = user_text.upper().split()
            found_symbol = None
            for w in words:
                if w in ["SST", "MTEN", "CPSH", "MVIS", "WGS", "NVDA", "AAPL", "TSLA", "AMZN"]:
                    found_symbol = w
                    break
            
            if found_symbol:
                stock_info = get_stock_data_summary(found_symbol)
                prompt = f"""
                المستخدم يسألك عن سهم {found_symbol} عبر التليجرام.
                إليك البيانات المباشرة الحالية:
                {stock_info}
                
                سؤال المستخدم الأصلي: "{user_text}"
                
                المطلوب: أجب بشكل خبير مالي واشرح الوضع الفني بأسلوب مبسط ومشجع باللغة العربية.
                """
                reply = await ask_gemini(prompt)
            else:
                prompt = f"""
                أنت وكيل تداول ذكي لمساعدة المستخدم في أسواق الأسهم والتحليل الفني.
                رسالة المستخدم: "{user_text}"
                أجب باللغة العربية بأسلوب ذكي ومختصر ومفيد جداً.
                """
                reply = await ask_gemini(prompt)
                
            await send_telegram_message(reply, chat_id)
    except Exception as e:
        print(f"خطأ في معالجة رسالة التليجرام: {e}")
        
    return {"status": "ok"}
