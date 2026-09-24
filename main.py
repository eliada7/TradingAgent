import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="TradingView AI Agent")

# --- ضع التوكين والـ ID الخاط بيك هنا لاحقاً ---
TELEGRAM_BOT_TOKEN = "8736155366:AAGy8375LQ-myDoXi6BAmN-xtr1jSs5rFlA"
TELEGRAM_CHAT_ID = "5156868751"

class SignalData(BaseModel):
    ticker: str
    price: float
    rsi: float
    timeframe: str
    action: str

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.status_code == 200

def analyze_signal(data: SignalData) -> str:
    if data.rsi < 30:
        analysis = "🟢 تشبع بيعي شديد (فرصة ارتداد صعودي)"
    elif data.rsi > 70:
        analysis = "🔴 تشبع شرائي شديد (احتمال جني أرباح/تصحيح)"
    else:
        analysis = "🟡 حركة متوازنة ضمن النطاق الطبيعي"

    report = (
        f"🚨 **تنبيه جديد من TradingView** 🚨\n\n"
        f"📌 **السهم:** `{data.ticker}`\n"
        f"⏱️ **الإطار الزمني:** {data.timeframe}\n"
        f"💰 **السعر الحالي:** ${data.price}\n"
        f"📊 **مؤشر RSI:** {data.rsi}\n"
        f"⚡ **الإجراء التلقائي:** `{data.action}`\n\n"
        f"🧠 **تحليل الـ Agent:**\n{analysis}\n"
    )
    return report

@app.post("/webhook")
async def handle_tradingview_webhook(request: Request):
    try:
        json_data = await request.json()
        data = SignalData(**json_data)
        report = analyze_signal(data)
        success = send_telegram_message(report)
        if success:
            return {"status": "success", "message": "Signal processed and sent to Telegram"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send Telegram message")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def home():
    return {"message": "TradingView AI Agent is running!"}