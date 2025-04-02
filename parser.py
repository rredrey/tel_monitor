# parser.py
import re

def find_token(message):
    """
    Находит токен в сообщении.
    Пример: $PAW, $SOL, $BTC
    """
    match = re.search(r"\$[A-Za-z0-9]+", message)
    return match.group(0) if match else None


def find_contract_address(message):
    """
    Находит контрактный адрес Solana.
    Приоритет отдается адресам после слова 'token/'.
    Если адреса после 'token/' нет, ищем адрес после 'CA:' или 'solana/'.
    """
    token_match = re.search(r"token/([a-zA-Z0-9]{32,})", message)
    if token_match:
        return token_match.group(1)

    ca_match = re.search(r"CA:\s*([a-zA-Z0-9]{32,})", message)
    if ca_match:
        return ca_match.group(1)

    solana_match = re.search(r"solana/([a-zA-Z0-9]{32,})", message)
    return solana_match.group(1) if solana_match else None


def find_links(message):
    """
    Находит ссылки в сообщении.
    Пример: https://x.com/pawcat_token, https://t.me/pawcat_token
    """
    matches = re.findall(r"https?://[^\s]+", message)
    return matches


def find_price_levels(message):
    """
    Находит уровни цен в сообщении.
    Пример: "around 1k-2k", "wait for 5-10"
    """
    matches = re.findall(
        r"(?:around|wait for|dip around|good entry is around)\s+(\d+k?)-(\d+k?)",
        message,
        re.IGNORECASE,
    )
    price_levels = []

    for match in matches:
        try:
            low = match[0].lower().rstrip("k")
            high = match[1].lower().rstrip("k")
            low_value = int(low) * 1000 if "k" in match[0].lower() else int(low)
            high_value = int(high) * 1000 if "k" in match[1].lower() else int(high)
            price_levels.append(f"{low_value}-{high_value}")
        except ValueError:
            continue

    return price_levels


def classify_signal(message):
    """
    Классифицирует сигнал на основе текста сообщения.
    Возвращает тип рекомендации: "Уверенный сигнал к покупке", "Рискованный сигнал к покупке", "Отложенный сигнал к покупке", "Нейтральное сообщение".
    """
    if re.search(
        r"(?:around|wait for|dip around|good entry is around)\s+(\d+k?-\d+k?)",
        message,
        re.IGNORECASE,
    ):
        return "Отложенный сигнал к покупке"

    if (
        "aped" in message
        or "ape" in message
        or "gambled" in message
        and ("hit" in message or "ATH" in message)
        or "hype" in message
        and "dip floor" in message
        or "good" in message.lower()
        or re.search(r"\b(buying|bought)\s+(here|this)", message, re.IGNORECASE)
        or re.search(r"\brug\s+me\s+or\s+give\s+me\s+\d+-\d+x\b", message, re.IGNORECASE)
    ):
        return "Уверенный сигнал к покупке"

    if (
        "DYOR and mind your own risk" in message
        or "DYOR and find your entry" in message
        or "near ATH" in message
        or "chart is near ATH" in message
        or "Moon or dust" in message
        or "moon or dust" in message
    ):
        return "Рискованный сигнал к покупке"

    if (
        "ticket is to bullish" in message
        or "Beta play" in message
        or "got reposted by" in message
        or "CZ" in message
        or "Binance" in message
        or "new concept" in message.lower()
        or "meme" in message.lower()
    ):
        return "Уверенный сигнал к покупке"

    return "Нейтральное сообщение"


def parse_message(message):
    """
    Анализирует сообщение и возвращает структурированные данные.
    """
    return {
        "token": find_token(message),
        "contract_address": find_contract_address(message),
        "links": find_links(message),
        "price_levels": find_price_levels(message),
        "recommendations": classify_signal(message),
    }
