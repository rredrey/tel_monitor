# trading/api.py
import requests
import logging

def get_current_price(token_address):
    try:
        response = requests.get(f"https://api.gmgn.ai/price/{token_address}")
        response.raise_for_status()
        return response.json().get("price", 0)
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка получения цены для токена {token_address}: {e}")
        return 0

def get_sol_price_in_usdt():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        response.raise_for_status()
        return response.json().get("solana", {}).get("usd", 150.0)
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка получения цены SOL: {e}")
        return 150.0
