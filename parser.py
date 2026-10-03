import os
import ccxt
from flask import Flask
import pandas as pd
from google import genai

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print(
    f"🔧 Проверка ключей на старте: TELEGRAM_TOKEN={'ОК' if TELEGRAM_TOKEN else 'ПУСТО'},"
    f" CHAT_ID={'ОК' if CHAT_ID else 'ПУСТО'},"
    f" GEMINI_KEY={'ОК' if GEMINI_API_KEY else 'ПУСТО'}"
)

app = Flask(__name__)


def send_telegram_message(message):
  if not TELEGRAM_TOKEN or not CHAT_ID:
    print(
        "❌ ОШИБКА: TELEGRAM_TOKEN или CHAT_ID пусты в переменных Render!"
    )
    return
  import requests

  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"📥 Ответ от Telegram API: {response.status_code} - {response.text}")
  except Exception as e:
    print(f"❌ Ошибка соединения с Telegram: {e}")


def get_ai_analysis(price, rsi, ema10, ema20):
  if not GEMINI_API_KEY:
    return "ИИ-анализ отключен (нет ключа)."

  try:
    # Безопасная инициализация клиента внутри функции
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"Ты профессиональный криптотрейдер. Данные по BTC/USD:\n- Цена:"
        f" ${price:,.2f}\n- RSI: {rsi:.2f}\n- EMA 10:${ema10:,.2f}\n- EMA 20:"
        f" ${ema20:,.2f}\nДай краткий вердикт по рынку (до 4 предложений) на"
        " русском языке."
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text
  except Exception as e:
    print(f"⚠️ Ошибка Gemini ИИ: {e}")
    return f"ИИ временно недоступен (ошибка ключа или лимита)."


def run_crypto_analysis():
  print("\n--- Запуск проверки рынка BTC через Kraken ---")
  try:
    exchange = ccxt.kraken()
    bars = exchange.fetch_ohlcv("BTC/USD", timeframe="1h", limit=50)

    df = pd.DataFrame(
        bars, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
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
        f"🤖 *ИИ-Агент по BTC/USD (Kraken)*\n\n💵 Цена: `${price:,.2f}`\n📊 RSI:"
        f" `{rsi:.2f}`\n📈 EMA 10: `{ema10:,.2f}`\n📉 EMA 20:"
        f" `{ema20:,.2f}`\n\n🧠 *Мнение ИИ:*\n{ai_commentary}"
    )

    send_telegram_message(signal_text)
    return (
        f"✅ Успешно! Цена: ${price:,.2f}, RSI: {rsi:.2f}, отчет отправлен в"
        " Telegram."
    )
  except Exception as e:
    err_msg = f"❌ Ошибка при анализе рынка: {e}"
    print(err_msg)
    return err_msg


@app.route("/")
def home():
  result = run_crypto_analysis()
  return (
      f"<h1>🤖 Crypto AI Agent</h1><p>{result}</p><hr><p>Система работает"
      " стабильно!</p>"
  )


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)