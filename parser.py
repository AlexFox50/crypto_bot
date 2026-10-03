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
    f"🔧 Проверка ключей: TELEGRAM_TOKEN={'ОК' if TELEGRAM_TOKEN else 'ПУСТО'},"
    f" CHAT_ID={'ОК' if CHAT_ID else 'ПУСТО'},"
    f" GEMINI_KEY={'ОК' if GEMINI_API_KEY else 'ПУСТО'}"
)

if GEMINI_API_KEY:
  ai_client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)


@app.route("/")
def home():
  return "🤖 Crypto AI Agent is running 24/7!"


def send_telegram_message(message):
  if not TELEGRAM_TOKEN or not CHAT_ID:
    print("❌ ОШИБКА: TELEGRAM_TOKEN или CHAT_ID не заданы в переменных Render!")
    return

  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}

  print(
      f"📤 Пытаемся отправить запрос в Telegram для CHAT_ID: {CHAT_ID}..."
  )  # Отладка
  try:
    response = requests.post(url, json=payload, timeout=10)
    print(
        f"📥 Ответ от Telegram API (Код статуса: {response.status_code}):"
        f" {response.text}"
    )

    if response.status_code == 200:
      print("✅ Уведомление УСПЕШНО доставлено в Telegram!")
    else:
      print("⚠️ Telegram отклонил сообщение! Проверьте правильность CHAT_ID.")
  except Exception as e:
    print(f"❌ Ошибка соединения с Telegram: {e}")


def get_ai_analysis(price, rsi, ema10, ema20):
  if not GEMINI_API_KEY:
    return "ИИ-анализ отключен."
  prompt = f"""
    Ты профессиональный криптотрейдер. Данные по BTC/USD:
    - Цена: ${price:,.2f}
    - RSI: {rsi:.2f}
    - EMA 10: ${ema10:,.2f}     - EMA 20:${ema20:,.2f}
    Дай краткий вердикт по рынку (до 4 предложений) на русском языке.
    """
  try:
    response = ai_client.models.generate_content(
        model="gemini-3.8-flash", contents=prompt
    )
    return response.text
  except Exception as e:
    print(f"Ошибка Gemini ИИ: {e}")
    return "ИИ временно недоступен."


def job_analyze_btc():
  print("\n--- Запуск плановой проверки рынка BTC ---")
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

    print(
        f"📊 Данные получены: Цена = ${price:,.2f}, RSI = {rsi:.2f}. Запрос к"
        " ИИ..."
    )
    ai_commentary = get_ai_analysis(price, rsi, ema10, ema20)

    signal_text = (
        f"🤖 *ИИ-Агент по BTC/USD (Render)*\n\n💵 Цена: `${price:,.2f}`\n📊 RSI:"
        f" `{rsi:.2f}`\n\n🧠 *Мнение ИИ:*\n{ai_commentary}"
    )

    send_telegram_message(signal_text)
  except Exception as e:
    print(f"❌ Ошибка в расчете рынка: {e}")


def run_scheduler():
  print("⏳ Ожидание 5 секунд до старта первой проверки...")
  time.sleep(5)
  job_analyze_btc()

  schedule.every(1).hours.do(job_analyze_btc)
  while True:
    schedule.run_pending()
    time.sleep(1)


# Запуск фонового потока
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)