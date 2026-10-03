import os
import ccxt
from flask import Flask
import pandas as pd
import requests
from google import genai

print("🚀 Старт приложения...")

app = Flask(__name__)


@app.route("/")
def home():
  print("\n--- Запрос на корневой URL получен ---")
  try:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # --- 1. Сбор данных по BTC (Kraken) ---
    btc_price, btc_rsi, btc_ema10, btc_ema20 = 0, 0, 0, 0
    try:
      exchange_kraken = ccxt.kraken({"timeout": 4000})
      bars_btc = exchange_kraken.fetch_ohlcv("BTC/USD", timeframe="1h", limit=30)
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
      print(f"⚠️ Ошибка BTC: {e}")

    # Подключаем Gate.io и загружаем рынки для умного поиска
    gram_price, gram_rsi, gram_ema10, gram_ema20 = 0, 0, 0, 0
    aztec_price, aztec_rsi, aztec_ema10, aztec_ema20 = 0, 0, 0, 0

    try:
      exchange_gate = ccxt.gate({"timeout": 5000})
      exchange_gate.load_markets()

      # Функция для безопасного поиска и сбора данных по альткоинам
      def fetch_gate_alt(symbol_candidate):
        symbol = None
        for s in [
            symbol_candidate,
            symbol_candidate.replace("/USDT", "/USDT:USDT"),
        ]:
          if s in exchange_gate.markets:
            symbol = s
            break
        if not symbol:
          # Ищем частичное совпадение
          for m in exchange_gate.markets:
            if symbol_candidate.split("/")[0] in m and "USDT" in m:
              symbol = m
              break

        if symbol:
          bars = exchange_gate.fetch_ohlcv(symbol, timeframe="1h", limit=30)
          df = pd.DataFrame(
              bars,
              columns=["timestamp", "open", "high", "low", "close", "volume"],
          )
          df["ema_10"] = df["close"].ewm(span=10, adjust=False).mean()
          df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
          delta = df["close"].diff()
          gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
          loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
          rs = gain / loss
          df["rsi"] = 100 - (100 / (1 + rs))
          last = df.iloc[-1]
          return last["close"], last["rsi"], last["ema_10"], last["ema_20"]
        return 0, 0, 0, 0

      # Сбор GRAM
      try:
        gram_price, gram_rsi, gram_ema10, gram_ema20 = fetch_gate_alt(
            "GRAM/USDT"
        )
      except Exception as ex:
        print(f"⚠️ Ошибка GRAM: {ex}")

      # Сбор AZTEC
      try:
        aztec_price, aztec_rsi, aztec_ema10, aztec_ema20 = fetch_gate_alt(
            "AZTEC/USDT"
        )
      except Exception as ex:
        print(f"⚠️ Ошибка AZTEC: {ex}")

    except Exception as e:
      print(f"⚠️ Ошибка подключения к Gate.io: {e}")

    # --- 2. Получение аналитики от ИИ ---
    ai_commentary = "ИИ-анализ временно недоступен."
    if GEMINI_API_KEY:
      try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"Ты профессиональный криптотрейдер. Данные:\n"
            f"1. BTC/USD (Kraken): Цена ${btc_price:,.2f}, RSI {btc_rsi:.2f}\n"
            f"2. GRAM (Gate.io): Цена ${gram_price:.4f}, RSI {gram_rsi:.2f}\n"
            f"3. AZTEC (Gate.io): Цена ${aztec_price:.4f}, RSI"
            f" {aztec_rsi:.2f}\n"
            "Дай краткий аналитический вердикт по активам (до 4 предложений) на"
            " русском языке."
        )
        response = client.models.generate_content(
            model="gemini-3.8-flash", contents=prompt
        )
        ai_commentary = response.text
      except Exception as ai_err:
        ai_commentary = "ИИ временно недоступен."

    # --- 3. Формирование отчета ---
    signal_text = (
        f"🤖 Крипто Агент (BTC, GRAM & AZTEC)\n\n"
        f"🪙 *BTC/USD (Kraken)*\n"
        f"💵 Цена: ${btc_price:,.2f}\n"
        f"📊 RSI: {btc_rsi:.2f}\n"
        f"📈 EMA 10/20: ${btc_ema10:,.2f} / ${btc_ema20:,.2f}\n\n"
        f"💎 *GRAM (Gate.io)*\n"
        f"💵 Цена: ${gram_price:.4f}\n"
        f"📊 RSI: {gram_rsi:.2f}\n"
        f"📈 EMA 10/20: ${gram_ema10:.4f} / ${gram_ema20:.4f}\n\n"
        f"🛡 *AZTEC (Gate.io)*\n"
        f"💵 Цена: ${aztec_price:.4f}\n"
        f"📊 RSI: {aztec_rsi:.2f}\n"
        f"📈 EMA 10/20: ${aztec_ema10:.4f} / ${aztec_ema20:.4f}\n\n"
        f"🧠 Мнение ИИ:\n{ai_commentary}"
    )

    # --- 4. Отправка в Telegram ---
    if TELEGRAM_TOKEN and CHAT_ID:
      url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
      payload = {"chat_id": CHAT_ID, "text": signal_text}
      requests.post(url, json=payload, timeout=5)

    return (
        f"<h1>🤖 Multi-Crypto Agent</h1><p>✅ Данные собраны, отчет отправлен"
        " в Telegram!</p>"
    )

  except Exception as e:
    err_msg = f"❌ Критическая ошибка: {e}"
    print(err_msg)
    return f"<h1>Ошибка</h1><p>{err_msg}</p>", 500


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🌐 Запуск Flask-сервера на порту {port}...")
  app.run(host="0.0.0.0", port=port)