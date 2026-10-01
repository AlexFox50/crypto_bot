import os
import time
import pandas as pd
import requests
import schedule
from google import genai

# --- НАСТРОЙКИ ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
TELEGRAM_TOKEN = os.getenv("8972434600:AAFWDKYNuvR-wTzXCBEhBK_-wLKdji6UOio")
CHAT_ID = os.getenv("6080127256")
GEMINI_API_KEY = os.getenv("AQ.Ab8RN6LiubsbfkwBqfph1fSbeAlwNFIUVzrrbaUHuDgk76VlVQ")

# Инициализация клиента Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_message(message):
    """Функция для отправки сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print("📤 Уведомление успешно отправлено в Telegram!")
        else:
            print(f"⚠ Ошибка отправки в Telegram: {response.text}")
    except requests.exceptions.Timeout:
        print("⏳ Превышено время ожидания при подключении к Telegram.")
    except Exception as e:
        print(f"Ошибка сети при отправке в Telegram: {e}")

def get_ai_analysis(price, rsi, ema10, ema20):
    """Запрос к ИИ для генерации экспертного анализа с защитой от перегрузки (503)"""
    prompt = f"""
    Ты профессиональный криптотрейдер и аналитик рынка. 
    Вот текущие технические данные по Биткоину (BTC/USD):
    - Текущая цена: ${price:,.2f}
    - RSI (14): {rsi:.2f}
    - EMA 10: ${ema10:,.2f}     - EMA 20:${ema20:,.2f}
    
    Дай короткий, структурированный и профессиональный вердикт по рынку (в стиле риск-менеджера). 
    Оцени, есть ли потенциальная точка для покупки (Long) или продажи (Short), учитывая текущий RSI и тренд. 
    Пиши на русском языке, не используй лишнюю воду, будь лаконичен (до 4-5 предложений).
    """
    
    # Делаем до 3 попыток в случае временной перегрузки серверов ИИ
    for attempt in range(3):
        try:
            response = ai_client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            print(f"Попытка {attempt + 1} связаться с ИИ не удалась: {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                return "ИИ временно перегружен, но технические индикаторы рассчитаны успешно."

def job_analyze_btc():
    """Основная задача агента: сбор данных, вызов ИИ и отправка отчета"""
    print("\n--- Запуск плановой проверки рынка BTC с ИИ-анализом ---")
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        prices = data['prices']
        df = pd.DataFrame(prices, columns=['timestamp', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        last_row = df.iloc[-1]
        price = last_row['close']
        rsi = last_row['rsi']
        ema10 = last_row['ema_10']
        ema20 = last_row['ema_20']
        
        print(f"Текущая цена BTC: ${price:,.2f} | RSI: {rsi:.2f}")
        print("Запрашиваем аналитический комментарий у ИИ...")
        
        ai_commentary = get_ai_analysis(price, rsi, ema10, ema20)
        
        signal_text = f"🤖 *ИИ-Агент по BTC/USD*\n\n" \
                      f"💵 Цена: `${price:,.2f}`\n" \
                      f"📊 RSI (14): `{rsi:.2f}`\n" \
                      f"📈 EMA 10: `{ema10:,.2f}`\n" \
                      f"📉 EMA 20: `{ema20:,.2f}`\n\n" \
                      f"🧠 *Мнение ИИ-аналитика:*\n{ai_commentary}"
            
        send_telegram_message(signal_text)

    except Exception as e:
        print(f"Ошибка при анализе рынка: {e}")

if __name__ == "__main__":
    print("🤖 ИИ-агент по Биткоину запущен в фоновом режиме...")
    
    # Первый тестовый запуск при старте
    job_analyze_btc()
    
    # Автозапуск каждый час
    schedule.every(1).hours.do(job_analyze_btc)
    
    while True:
        schedule.run_pending()
        time.sleep(1)