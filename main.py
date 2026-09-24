async def ask_gemini(prompt: str) -> str:
    """استدعاء ذكي لـ Gemini API مع طباعة تشخيصية للخطأ"""
    if not GEMINI_API_KEY:
        return "⚠️ مفتاح `GEMINI_API_KEY` غير مفعّل في متغيرات البيئة بـ Render."
    
    clean_key = GEMINI_API_KEY.strip()
    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    errors = []
    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    errors.append(f"{model}: HTTP {response.status_code}")
            except Exception as e:
                errors.append(f"{model}: {str(e)}")
                
    return f"⚠️ تعذر معالجة الطلب عبر الذكاء الاصطناعي.\nتشخيص الخطأ من جوجل: {', '.join(errors)}"
