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

    # --- 1. Сбор данных по BTC (Kraken) ---
    exchange_btc = ccxt.kraken()
    bars_btc = exchange_btc.fetch_ohlcv("BTC/USD", timeframe="1h", limit=50)

    df_btc = pd.DataFrame(
        bars_btc,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df_btc["ema_10"] = df_btc["close"].ewm(span=10, adjust=False).mean()
    df_btc["ema_20"] = df_btc["close"].ewm(span=20, adjust=False).mean()

    delta_btc = df_btc["close"].diff()
    gain_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean()
    loss_btc = (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    rs_btc = gain_btc / loss_btc
    df_btc["rsi"] = 100 - (100 / (1 + rs_btc))

    last_btc = df_btc.iloc[-1]
    btc_price, btc_rsi = last_btc["close"], last_btc["rsi"]
    btc_ema10, btc_ema20 = last_btc["ema_10"], last_btc["ema_20"]

    # --- 2. Сбор данных по GRAM (Gate.io) ---
    exchange_gram = ccxt.gate()
    bars_gram = exchange_gram.fetch_ohlcv("GRAM/USDT", timeframe="1h", limit=50)

    df_gram = pd.DataFrame(
        bars_gram,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df_gram["ema_10"] = df_gram["close"].ewm(span=10, adjust=False).mean()
    df_gram["ema_20"] = df_gram["close"].ewm(span=20, adjust=False).mean()

    delta_gram = df_gram["close"].diff()
    gain_gram = (delta_gram.where(delta_gram > 0, 0)).rolling(window=14).mean()
    loss_gram = (-delta_gram.where(delta_gram < 0, 0)).rolling(window=14).mean()
    rs_gram = gain_gram / loss_gram
    df_gram["rsi"] = 100 - (100 / (1 + rs_gram))

    last_gram = df_gram.iloc[-1]
    gram_price, gram_rsi = last_gram["close"], last_gram["rsi"]
    gram_ema10, gram_ema20 = last_gram-val = (
        last_gram["ema_10"],
        last_gram["ema_20"],
    )

    # --- 3. Получение аналитики от ИИ ---
    ai_commentary = "ИИ-анализ временно недоступен."
    if GEMINI_API_KEY:
      try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"Ты профессиональный криптотрейдер. Данные:\n"
            f"1. BTC/USD: Цена ${btc_price:,.2f}, RSI {btc_rsi:.2f}\n"
            f"2. GRAM/USDT: Цена ${gram_price:.4f}, RSI {gram_rsi:.2f}\n"
            "Дай краткий аналитический вердикт по обоим активам (до 5"
            " предложений) на русском языке."
        )
        response = client.models.generate_content(
            model="gemini-3.8-flash", contents=prompt
        )
        ai_commentary = response.text
      except Exception as ai_err:
        ai_commentary = f"ИИ пропущен (ошибка лимита/сети)."

    # --- 4. Формирование отчета ---
    signal_text = (
        f"🤖 Крипто Агент (BTC & GRAM)\n\n"
        f"🪙 *BTC/USD (Kraken)*\n"
        f"💵 Цена: ${btc_price:,.2f}\n"
        f"📊 RSI: {btc_rsi:.2f}\n"
        f"📈 EMA 10/20: ${btc_ema10:,.2f} / ${btc_ema20:,.2f}\n\n"
        f"💎 *GRAM/USDT (Gate.io)*\n"
        f"💵 Цена: ${gram_price:.4f}\n"
        f"📊 RSI: {gram_rsi:.2f}\n"
        f"📈 EMA 10/20: ${gram_ema10:.4f} / ${gram_ema20:.4f}\n\n"
        f"🧠 Мнение ИИ:\n{ai_commentary}"
    )

    # --- 5. Отправка в Telegram ---
    if TELEGRAM_TOKEN and CHAT_ID:
      url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
      payload = {"chat_id": CHAT_ID, "text": signal_text}
      resp = requests.post(url, json=payload, timeout=10)
      print(f"📥 Telegram API status: {resp.status_code}")

    return (
        f"<h1>🤖 Multi-Crypto Agent</h1><p>✅ BTC: ${btc_price:,.2f} | GRAM:"
        f" ${gram_price:.4f} — Отправлено в Telegram!</p>"
    )

  except Exception as e:
    err_msg = f"❌ Ошибка: {e}"
    print(err_msg)
    return f"<h1>Ошибка</h1><p>{err_msg}</p>", 500


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)