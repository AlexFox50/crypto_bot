import os
from flask import Flask

print("🚀 Старт легкого Flask-сервера...")

app = Flask(__name__)


@app.route("/")
def home():
  print("\n--- Запрос получен, загружаем модули и данные ---")
  try:
    # Ленивые импорты (загружаются только при вызове, не вешая старт сервера)
    import ccxt
    import pandas as pd
    import requests
    from google import genai

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Сбор данных по BTC (Kraken)
    btc_price, btc_rsi, btc_ema10, btc_ema20 = 0, 0, 0, 0
    try:
      exchange = ccxt.kraken({"timeout": 3000})
      bars_btc = exchange.fetch_ohlcv("BTC/USD", timeframe="1h", limit=30)
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
    except Exception as e:
      print(f"⚠️ Ошибка сбора данных: {e}")

    # Анализ ИИ
    ai_commentary = "ИИ-анализ отключен."
    if GEMINI_API_KEY:
      try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"Ты криптотрейдер. BTC/USD: Цена ${btc_price:,.2f}, RSI"
            f" {btc_rsi:.2f}. Дай краткий вердикт (до 2 предложений) на рус."
        )
        response = client.models.generate_content(
            model="gemini-3.8-flash", contents=prompt
        )
        ai_commentary = response.text
      except Exception:
        ai_commentary = "ИИ временно недоступен."

    # Отправка в Telegram
    signal_text = (
        f"🤖 Крипто Агент (Kraken)\n\n"
        f"🪙 *BTC/USD*\n"
        f"💵 Цена: ${btc_price:,.2f}\n"
        f"📊 RSI: {btc_rsi:.2f}\n"
        f"📈 EMA 10/20: ${btc_ema10:,.2f} / ${btc_ema20:,.2f}\n\n"
        f"🧠 Мнение ИИ:\n{ai_commentary}"
    )

    if TELEGRAM_TOKEN and CHAT_ID:
      url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
      requests.post(
          url, json={"chat_id": CHAT_ID, "text": signal_text}, timeout=5
      )

    return (
        f"<h1>🤖 Crypto Agent</h1><p>✅ Успешно! Цена BTC: ${btc_price:,.2f},"
        " отчет отправлен в Telegram.</p>"
    )

  except Exception as e:
    err_msg = f"❌ Ошибка обработчика: {e}"
    print(err_msg)
    return f"<h1>Ошибка</h1><p>{err_msg}</p>", 500


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск веб-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)