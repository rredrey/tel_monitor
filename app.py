# app.py
import tkinter as tk
from guii import TradingBotGUI  # Импортируем класс TradingBotGUI из файла guii.py
import asyncio
from telethon import TelegramClient
import config
import parser
from trading import (
    load_wallet,
    check_balance,
    swap_tokens,
    sell_tokens,
    get_current_price,
    DEMO_WALLET,
    PURCHASE_PRICES,
)
import threading
import time
import requests
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()],
)


def send_notification(message):
    """Отправляет уведомление в Telegram."""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {"chat_id": config.NOTIFICATION_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info(f"Уведомление отправлено: {message}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления: {str(e)}")


async def monitor_telegram(app_instance):
    """Мониторинг Telegram-канала."""
    telegram_client = TelegramClient('session', config.API_ID, config.API_HASH)
    await telegram_client.start()
    app_instance.log(f"Мониторинг канала {config.TELEGRAM_CHANNEL} начат.")
    while app_instance.monitoring:
        try:
            async for message in telegram_client.iter_messages(config.TELEGRAM_CHANNEL, limit=1):
                if message.text:
                    signal = parser.parse_message(message.text)
                    if "покупке" in signal["recommendations"] and signal["contract_address"]:
                        app_instance.execute_swap(signal)
                    else:
                        app_instance.log("Ошибка: Сигнал не распознан или не для покупки.")
        except Exception as e:
            logging.error(f"Ошибка мониторинга Telegram: {str(e)}")
            await asyncio.sleep(10)


def profit_monitoring_task(app_instance):
    """Фоновая задача для мониторинга прибыли."""
    while True:
        try:
            if app_instance.profit_monitoring:
                for token_mint in list(DEMO_WALLET["tokens"].keys()):
                    try:
                        current_price = get_current_price(token_mint, app_instance.wallet)
                        purchase_price = PURCHASE_PRICES.get(token_mint, 0)
                        if purchase_price > 0 and current_price >= purchase_price * float(app_instance.profit_target_entry.get()):
                            amount = DEMO_WALLET["tokens"][token_mint]
                            swap_tokens(app_instance.wallet, token_mint, "So11111111111111111111111111111111111111112", int(amount * 1_000_000_000))
                            app_instance.log(f"Токен {token_mint} продан с прибылью.")
                            del DEMO_WALLET["tokens"][token_mint]
                            del PURCHASE_PRICES[token_mint]
                    except Exception as e:
                        logging.error(f"Критическая ошибка при проверке токена {token_mint}: {str(e)}")
                        time.sleep(60)
            time.sleep(60)
        except Exception as e:
            logging.error(f"Ошибка в profit_monitoring_task: {str(e)}")
            time.sleep(60)


def main():
    """Основная функция для запуска приложения."""
    root = tk.Tk()
    app = TradingBotGUI(root)  # Теперь класс TradingBotGUI доступен через импорт

    # Запуск фоновых задач
    threading.Thread(target=profit_monitoring_task, args=(app,), daemon=True).start()
    asyncio.run(monitor_telegram(app))

    root.mainloop()


if __name__ == "__main__":
    main()
