import os
from flask import Flask

print("🚀 Старт приложения...")

app = Flask(__name__)


@app.route("/")
def home():
  print("\n--- Запрос на корневой URL получен ---")
  try:
    import ccxt
    import pandas as pd
    import requests
    from google import genai

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # 1. Сбор данных с Kraken
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

    # 2. Получение ответа от ИИ
    ai_commentary = "ИИ-анализ отключен."
    if GEMINI_API_KEY:
      try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"Ты профессиональный криптотрейдер. Данные по BTC/USD:\n- Цена:"
            f" ${price:,.2f}\n- RSI: {rsi:.2f}\n- EMA 10: ${ema10:,.2f}\n- EMA"
            f" 20: ${ema20:,.2f}\nДай краткий вердикт по рынку (до 4"
            " предложений) на русском языке."
        )
        response = client.models.generate_content(
    model="gemini-1.5-flash", contents=prompt
)
        ai_commentary = response.text
      except Exception as ai_err:
        ai_commentary = f"ИИ временно недоступен ({str(ai_err)[:30]})."

    # 3. Формирование текста (без спецсимволов Markdown)
    signal_text = (
        f"🤖 ИИ-Агент по BTC/USD (Kraken)\n\n"
        f"💵 Цена: ${price:,.2f}\n"
        f"📊 RSI: {rsi:.2f}\n"
        f"📈 EMA 10: ${ema10:,.2f}\n"
        f"📉 EMA 20: ${ema20:,.2f}\n\n"
        f"🧠 Мнение ИИ:\n{ai_commentary}"
    )

    # 4. Отправка в Telegram как чистый текст (без parse_mode)
    if TELEGRAM_TOKEN and CHAT_ID:
      url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
      payload = {
          "chat_id": CHAT_ID,
          "text": signal_text,
      }  # Убрали parse_mode, чтобы Telegram не отклонял текст
      resp = requests.post(url, json=payload, timeout=10)
      print(
          f"📥 Ответ от Telegram API: {resp.status_code} | Текст ответа:"
          f" {resp.text}"
      )

    return (
        f"<h1>🤖 Crypto AI Agent</h1><p>✅ Успешно! Цена: ${price:,.2f}, RSI:"
        f" {rsi:.2f}, отчет отправлен в Telegram.</p>"
    )

  except Exception as e:
    err_msg = f"❌ Ошибка в обработчике: {e}"
    print(err_msg)
    return f"<h1>Ошибка</h1><p>{err_msg}</p>", 500


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)