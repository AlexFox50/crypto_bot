import os
import threading
import time
from flask import Flask
import pandas as pd
import requests
import schedule
from google import genai

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print(
    f"🔧 Проверка ключей при старте: TELEGRAM_TOKEN={'УСТАНОВЛЕН' if TELEGRAM_TOKEN else 'ПУСТО!'},"
    f" CHAT_ID={'УСТАНОВЛЕН' if CHAT_ID else 'ПУСТО!'}"
)

if GEMINI_API_KEY:
  ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
  print("⚠ ВНИМАНИЕ: GEMINI_API_KEY не задан!")

# 1. Создаем Flask-приложение
app = Flask(__name__)


@app.route("/")
def home():
  return "🤖 Crypto AI Agent is running 24/7!"


def send_telegram_message(message):
  if not TELEGRAM_TOKEN or not CHAT_ID:
    print("❌ Невозможно отправить в Telegram: токен или chat_id не заданы!")
    return
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload, timeout=5)
    if response.status_code == 200:
      print("📤 Уведомление успешно отправлено в Telegram!")
    else:
      print(f"⚠ Ошибка отправки в Telegram: {response.text}")
  except Exception as e:
    print(f"Ошибка Telegram: {e}")


def get_ai_analysis(price, rsi, ema10, ema20):
  if not GEMINI_API_KEY:
    return "ИИ-анализ отключен (не задан GEMINI_API_KEY)."

  prompt = f"""
    Ты профессиональный криптотрейдер и аналитик рынка. 
    Вот текущие технические данные по Биткоину (BTC/USD):
    - Текущая цена: ${price:,.2f}
    - RSI (14): {rsi:.2f}
    - EMA 10: ${ema10:,.2f}     - EMA 20:${ema20:,.2f}
    
    Дай короткий, структурированный и профессиональный вердикт по рынку (в стиле риск-менеджера). 
    Оцени, есть ли потенциальная точка для покупки (Long) или продажи (Short), учитывая текущий RSI и тренд. 
    Пиши на русском языке, будь лаконичен (до 4-5 предложений).
    """
  for attempt in range(3):
    try:
      response = ai_client.models.generate_content(
          model="gemini-3.8-flash", contents=prompt
      )
      return response.text
    except Exception as e:
      print(f"Попытка запроса к ИИ {attempt + 1} не удалась: {e}")
      if attempt < 2:
        time.sleep(2)
      else:
        return (
            "ИИ временно перегружен, но технические индикаторы рассчитаны"
            " успешно."
        )


def job_analyze_btc():
  print("\n--- Запуск плановой проверки рынка BTC с ИИ-анализом ---")
  try:
    url = (
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30"
    )
    response = requests.get(url, timeout=10)
    data = response.json()

    prices = data["prices"]
    df = pd.DataFrame(prices, columns=["timestamp", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    df["ema_10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    last_row = df.iloc[-1]
    price = last_row["close"]
    rsi = last_row["rsi"]
    ema10 = last_row["ema_10"]
    ema20 = last_row["ema_20"]

    print(f"Успешно собрали данные: Цена BTC = ${price:,.2f}, RSI = {rsi:.2f}")

    ai_commentary = get_ai_analysis(price, rsi, ema10, ema20)

    signal_text = (
        f"🤖 *ИИ-Агент по BTC/USD (Render Free)*\n\n💵 Цена: `${price:,.2f}`\n📊"
        f" RSI (14): `{rsi:.2f}`\n📈 EMA 10: `{ema10:,.2f}`\n📉 EMA 20:"
        f" `{ema20:,.2f}`\n\n🧠 *Мнение ИИ-аналитика:*\n{ai_commentary}"
    )

    send_telegram_message(signal_text)
  except Exception as e:
    print(f"❌ Ошибка при анализе рынка: {e}")


def run_scheduler():
  print("⏳ Фоновый поток ожидает старта (пауза 5 сек)...")
  time.sleep(5)
  print("🚀 Фоновый поток начинает первую проверку...")

  job_analyze_btc()

  schedule.every(1).hours.do(job_analyze_btc)
  while True:
    schedule.run_pending()
    time.sleep(1)


if __name__ == "__main__":
  print("🤖 Запуск главного скрипта...")
  # Запускаем агента в фоновом потоке
  t = threading.Thread(target=run_scheduler, daemon=True)
  t.start()

  # Запуск Flask-сервера
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)
