# config.py

import os
import json

# Константы конфигурации
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
API_ID = "29281739"
API_HASH = "44c9b40fa8c0fb4594ffcf039e1e90ac"
TELEGRAM_CHANNEL = "MarkDegen"
PRIVATE_KEY = [76, 165, 72, 224, 33, 9, 232, 188, 179, 50, 169, 16, 244, 135, 119, 58, 199, 172, 141, 239, 53, 16, 149, 154, 74, 83, 136, 211, 27, 10, 245, 151, 131, 145, 15, 125, 55, 50, 135, 137, 206, 194, 69, 115, 69, 177, 221, 182, 13, 22, 64, 133, 57, 80, 255, 42, 24, 220, 68, 67, 15, 127, 69, 112]
DEMO_MODE = True
BOT_TOKEN = "7522907574:AAHfKJSGi4b0fbRldbtAG_4PL3fFivyo9Ic"
TELEGRAM_BOT_TOKEN = "7522907574:AAHfKJSGi4b0fbRldbtAG_4PL3fFivyo9Ic"
TELEGRAM_CHAT_ID = "1516301800"
NOTIFICATION_CHAT_ID = "1516301800"
PUMP_PORTAL_API_KEY = "cha34xvudcr6cmuj6nhnck2f8t9pevanddqq2xbeexd4rv3jetq2ymupet8ncu9k5dk7gjafet43jdb3edtpjj3j8wu78nv88dvn0x9h9tc4jdk3etd7ectk8ntk4uvqf99p2aur84yku6mw7aaugcnu6pt3g99a6wxk3a86dx6mc21e193gj9nf13qcykea5v6epa6e1vkuf8"

def load_config():
    """
    Загружает конфигурацию из переменных окружения или файла.
    Если переменные окружения не установлены, используются значения по умолчанию.
    """
    config_data = {
        "SOLANA_RPC_URL": os.getenv("SOLANA_RPC_URL", SOLANA_RPC_URL),
        "API_ID": os.getenv("API_ID", API_ID),
        "API_HASH": os.getenv("API_HASH", API_HASH),
        "TELEGRAM_CHANNEL": os.getenv("TELEGRAM_CHANNEL", TELEGRAM_CHANNEL),
        "PRIVATE_KEY": os.getenv("PRIVATE_KEY", PRIVATE_KEY),
        "DEMO_MODE": os.getenv("DEMO_MODE", DEMO_MODE),
        "BOT_TOKEN": os.getenv("BOT_TOKEN", BOT_TOKEN),
        "NOTIFICATION_CHAT_ID": os.getenv("NOTIFICATION_CHAT_ID", NOTIFICATION_CHAT_ID),
    }

    # Преобразование типов данных
    if isinstance(config_data["PRIVATE_KEY"], str):
        try:
            config_data["PRIVATE_KEY"] = json.loads(config_data["PRIVATE_KEY"])
        except json.JSONDecodeError:
            raise ValueError("Неверный формат PRIVATE_KEY. Ожидается список чисел.")

    if isinstance(config_data["DEMO_MODE"], str):
        config_data["DEMO_MODE"] = config_data["DEMO_MODE"].lower() in ("true", "1", "yes")

    return config_data
