import json
import math
import time
import requests
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
import base64
from cachetools import TTLCache
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from datetime import datetime
import base58
import config

# Глобальные переменные
DEMO_WALLET = {
    "SOL": 10.0,
    "tokens": {}
}
PURCHASE_PRICES = {}
API_CACHE = TTLCache(maxsize=500, ttl=300)
PRICE_CACHE = TTLCache(maxsize=1, ttl=300)
LAST_SUCCESSFUL_PRICES = {}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

client = Client(config.SOLANA_RPC_URL)

def load_wallet():
    """
    Загружает кошелек Solana из приватного ключа.
    Если DEMO_MODE включен, возвращает демо-кошелек.
    """
    if config.DEMO_MODE:
        # Возвращаем демо-кошелек
        return DEMO_WALLET
    else:
        try:
            # Проверяем, что PRIVATE_KEY является списком
            if not isinstance(config.PRIVATE_KEY, list):
                raise ValueError("PRIVATE_KEY должен быть списком байтов.")

            # Преобразуем список в байты
            private_key_bytes = bytes(config.PRIVATE_KEY)
            wallet = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Кошелек загружен: {wallet.pubkey()}")
            return wallet
        except Exception as e:
            logger.error(f"Ошибка загрузки кошелька: {str(e)}")
            raise Exception(f"Ошибка загрузки кошелька: {str(e)}")

def check_balance(wallet):
    """
    Проверяет баланс SOL на кошельке.
    """
    if config.DEMO_MODE:
        return wallet["SOL"] if isinstance(wallet, dict) else DEMO_WALLET["SOL"]

    try:
        balance = client.get_balance(wallet.pubkey())["result"]["value"] / 1_000_000_000
        logger.info(f"Баланс SOL: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Ошибка проверки баланса: {str(e)}")
        raise Exception(f"Ошибка проверки баланса: {str(e)}")

def check_token_balance(wallet: Keypair, token_mint: str) -> float:
    """Проверяет баланс токена в кошельке"""
    if config.DEMO_MODE:
        return DEMO_WALLET["tokens"].get(token_mint, 0.0)
    
    try:
        pubkey = Pubkey.from_string(token_mint)
        accounts = client.get_token_accounts_by_owner(wallet.pubkey(), {"mint": pubkey})
        if not accounts.value:
            return 0.0
        amount = accounts.value[0].account.data.parsed["info"]["tokenAmount"]["uiAmount"]
        return amount
    except Exception as e:
        logger.error(f"Ошибка проверки баланса токена {token_mint}: {str(e)}")
        raise Exception(f"Ошибка проверки баланса токена: {str(e)}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def get_sol_price():
    """Получает цену SOL с кэшированием"""
    if "sol_price" in PRICE_CACHE:
        logger.debug("Используется кэшированная цена SOL")
        return PRICE_CACHE["sol_price"]
    
    try:
        logger.info("Запрашиваем цену SOL через CoinGecko...")
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
            timeout=5
        )
        response.raise_for_status()
        sol_price = float(response.json().get("solana", {}).get("usd", 0))
        
        # Сохраняем результат в кэш
        PRICE_CACHE["sol_price"] = sol_price
        LAST_SUCCESSFUL_PRICES["SOL"] = sol_price
        logger.info(f"Получена новая цена SOL: {sol_price} USDT")
        return sol_price
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка получения цены SOL: {e}")
        return LAST_SUCCESSFUL_PRICES.get("SOL", 150.0)  # Возвращаем последнее успешное значение или 150 по умолчанию

def get_sol_price_in_usdt():
    """Алиас для get_sol_price для совместимости"""
    return get_sol_price()

def cache_api_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = f"{func.__name__}:{args[0]}"
        if cache_key in API_CACHE:
            logger.debug(f"Используется кэшированный ответ для {cache_key}")
            return API_CACHE[cache_key]
        
        result = func(*args, **kwargs)
        if result is not None and result != 0:
            API_CACHE[cache_key] = result
            LAST_SUCCESSFUL_PRICES[args[0]] = result
        return result
    return wrapper

@cache_api_response
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def get_token_price_from_pump_fun(token_mint: str) -> float:
    """Получает цену токена с Pump.fun"""
    try:
        logger.info(f"Запрос цены токена {token_mint[:6]}...{token_mint[-6:]} через Pump.fun...")
        url = f"https://api.pump.fun/coins/{token_mint}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("complete", False):
            logger.warning("Токен завершил торговлю на Pump.fun")
            return 0.0

        virtual_sol_reserves = data.get("virtual_sol_reserves", 0)
        virtual_token_reserves = data.get("virtual_token_reserves", 0)
        if virtual_token_reserves == 0:
            logger.warning("Нулевые резервы токенов")
            return 0.0
        
        price = virtual_sol_reserves / virtual_token_reserves
        logger.info(f"Цена токена {token_mint[:6]}...{token_mint[-6:]} через Pump.fun: {price:.8f} SOL")
        return price
    except Exception as e:
        logger.warning(f"Не удалось получить цену через Pump.fun: {str(e)}")
        return LAST_SUCCESSFUL_PRICES.get(token_mint, 0.0)

@cache_api_response
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def get_token_price_from_dexscreener(token_mint: str) -> float:
    """Получает цену токена через DexScreener"""
    try:
        logger.info(f"Запрос цены токена {token_mint[:6]}...{token_mint[-6:]} через DexScreener...")
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("pairs"):
            logger.warning(f"Не найдены торговые пары для токена {token_mint[:6]}...{token_mint[-6:]}")
            return 0.0

        best_pair = None
        max_liquidity = 0
        
        for pair in data["pairs"]:
            if pair["quoteToken"]["address"] == "So11111111111111111111111111111111111111112":
                liquidity = float(pair["liquidity"]["usd"] if "liquidity" in pair else 0)
                if liquidity > max_liquidity:
                    max_liquidity = liquidity
                    best_pair = pair

        if best_pair:
            price = float(best_pair["priceNative"])
            logger.info(f"Цена токена {token_mint[:6]}...{token_mint[-6:]} на {best_pair['dexId']}: {price:.8f} SOL")
            return price
            
        logger.warning("Не найдено подходящих торговых пар")
        return 0.0
    except Exception as e:
        logger.warning(f"Ошибка получения цены через DexScreener: {str(e)}")
        return LAST_SUCCESSFUL_PRICES.get(token_mint, 0.0)

def get_current_price(token_mint: str, wallet: Keypair = None) -> float:
    """Получает текущую цену токена"""
    logger.info(f"Получение текущей цены для токена {token_mint[:6]}...{token_mint[-6:]}")
    
    # Сначала пробуем DexScreener
    price = get_token_price_from_dexscreener(token_mint)
    if price > 0:
        return price
    
    # Затем Pump.fun
    if token_mint.lower().endswith('pump'):
        price = get_token_price_from_pump_fun(token_mint)
        if price > 0:
            return price
    
    # И наконец GMGN.ai для реального режима
    if not config.DEMO_MODE and wallet:
        try:
            logger.info(f"Попытка получить цену через GMGN.ai для токена {token_mint[:6]}...{token_mint[-6:]}")
            GMGN_API_HOST = "https://gmgn.ai"
            url = f"{GMGN_API_HOST}/defi/router/v1/sol/tx/get_swap_route?token_in_address={token_mint}&token_out_address=So11111111111111111111111111111111111111112&in_amount=1000000000&from_address={wallet.pubkey()}&slippage=0.5"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            quote = response.json()
            if quote["code"] == 0:
                price = int(quote["data"]["quote"]["outAmount"]) / 1_000_000_000
                logger.info(f"Цена через GMGN.ai: {price:.8f} SOL")
                return price
        except Exception as e:
            logger.warning(f"Ошибка получения цены через GMGN.ai: {str(e)}")
    
    logger.warning(f"Не удалось получить цену для токена {token_mint[:6]}...{token_mint[-6:]}")
    return LAST_SUCCESSFUL_PRICES.get(token_mint, 0.0)

def demo_buy_token(token_mint: str, amount_in_sol: float) -> dict:
    """Эмулирует покупку токена в демо-режиме"""
    try:
        current_price = get_current_price(token_mint)
        if current_price == 0:
            return {
                "status": "error",
                "message": f"Не удалось получить цену токена {token_mint[:6]}...{token_mint[-6:]}"
            }

        if DEMO_WALLET["SOL"] < amount_in_sol:
            return {
                "status": "error",
                "message": "Недостаточно SOL в демо-кошельке"
            }

        token_amount = amount_in_sol / current_price
        DEMO_WALLET["SOL"] -= amount_in_sol
        DEMO_WALLET["tokens"][token_mint] = DEMO_WALLET["tokens"].get(token_mint, 0.0) + token_amount
        PURCHASE_PRICES[token_mint] = current_price

        logger.info(f"Демо-покупка: {token_amount:.4f} токенов {token_mint[:6]}...{token_mint[-6:]} за {amount_in_sol} SOL по цене {current_price:.8f} SOL за токен")

        return {
            "status": "success",
            "token_amount": token_amount,
            "price_in_sol": current_price,
            "message": f"Куплено {token_amount:.4f} токенов по цене {current_price:.8f} SOL"
        }
    except Exception as e:
        logger.error(f"Ошибка демо-покупки: {str(e)}")
        return {
            "status": "error",
            "message": f"Ошибка демо-покупки: {str(e)}"
        }

def demo_sell_token(token_mint: str, profit_target: float, sell_percentage: float = 1.0) -> dict:
    """Эмулирует продажу токена в демо-режиме"""
    try:
        current_price = get_current_price(token_mint)
        if current_price == 0.0:
            return {
                "status": "error",
                "message": f"Не удалось получить текущую цену токена {token_mint[:6]}...{token_mint[-6:]}"
            }

        purchase_price = PURCHASE_PRICES.get(token_mint, 0.0)
        if purchase_price == 0.0:
            return {
                "status": "error",
                "message": f"Цена покупки для токена {token_mint[:6]}...{token_mint[-6:]} неизвестна"
            }

        token_amount = DEMO_WALLET["tokens"].get(token_mint, 0.0)
        if token_amount <= 0:
            return {
                "status": "error",
                "message": f"Нулевой баланс токена {token_mint[:6]}...{token_mint[-6:]}"
            }

        profit_ratio = current_price / purchase_price
        sell_amount = token_amount * sell_percentage

        if profit_ratio < profit_target:
            return {
                "status": "waiting",
                "message": f"Текущая прибыль {profit_ratio:.2f}x, ждём достижения {profit_target}x",
                "current_price": current_price,
                "profit_ratio": profit_ratio
            }

        sol_received = sell_amount * current_price
        DEMO_WALLET["SOL"] += sol_received
        DEMO_WALLET["tokens"][token_mint] -= sell_amount

        if DEMO_WALLET["tokens"][token_mint] <= 0:
            del DEMO_WALLET["tokens"][token_mint]
            if token_mint in PURCHASE_PRICES:
                del PURCHASE_PRICES[token_mint]

        logger.info(f"Демо-продажа: {sell_amount:.4f} токенов {token_mint[:6]}...{token_mint[-6:]} за {sol_received:.4f} SOL (прибыль: {profit_ratio:.2f}x)")

        return {
            "status": "sold",
            "sol_received": sol_received,
            "profit_ratio": profit_ratio,
            "message": f"Продано {sell_amount:.4f} токенов за {sol_received:.4f} SOL (прибыль: {profit_ratio:.2f}x)"
        }
    except Exception as e:
        logger.error(f"Ошибка при продаже токена {token_mint[:6]}...{token_mint[-6:]}: {str(e)}")
        return {
            "status": "error",
            "message": f"Ошибка при продаже токена: {str(e)}"
        }

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def swap_on_pump_fun(wallet: Keypair, input_mint: str, output_mint: str, amount: int, action: str = "BUY") -> dict:
    """Выполняет своп через Pump.fun API"""
    url = f"https://pumpportal.fun/api/trade?api-key={config.PUMP_PORTAL_API_KEY}"
    slippage = 0.5
    priority_fee = 0.00005
    denominated_in_sol = "true" if action == "BUY" else "false"
    amount_to_trade = amount if action == "BUY" else str(amount)

    data = {
        "action": action.lower(),
        "mint": output_mint if action == "BUY" else input_mint,
        "amount": amount_to_trade,
        "denominatedInSol": denominated_in_sol,
        "slippage": slippage * 100,
        "priorityFee": priority_fee,
        "pool": "pump"
    }

    try:
        logger.info(f"Попытка свопа через PumpPortal: {action} {output_mint if action == 'BUY' else input_mint}")
        response = requests.post(url, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()

        if "error" in result or "errors" in result:
            error_message = result.get("error", result.get("errors", "Неизвестная ошибка"))
            raise Exception(f"Ошибка в ответе PumpPortal: {error_message}")

        input_amount_sol = float(result.get("amountIn", result.get("inputAmount", 0))) / 1_000_000_000
        output_amount = float(result.get("amountOut", result.get("outputAmount", 0))) / 1_000_000_000

        if config.DEMO_MODE:
            if action == "BUY":
                if DEMO_WALLET["SOL"] >= input_amount_sol:
                    DEMO_WALLET["SOL"] -= input_amount_sol
                    DEMO_WALLET["tokens"][output_mint] = DEMO_WALLET["tokens"].get(output_mint, 0.0) + output_amount
                    PURCHASE_PRICES[output_mint] = input_amount_sol / output_amount if output_amount > 0 else 0
                    return {
                        "status": "success",
                        "demo_message": f"Демо-своп (покупка): {input_amount_sol} SOL -> {output_amount} токенов ({output_mint[:6]}...{output_mint[-6:]})"
                    }
                raise Exception("Недостаточно SOL в демо-кошельке")
            else:
                token_balance = DEMO_WALLET["tokens"].get(input_mint, 0.0)
                if token_balance >= output_amount:
                    DEMO_WALLET["tokens"][input_mint] -= output_amount
                    DEMO_WALLET["SOL"] += input_amount_sol
                    if DEMO_WALLET["tokens"][input_mint] <= 0:
                        del DEMO_WALLET["tokens"][input_mint]
                        if input_mint in PURCHASE_PRICES:
                            del PURCHASE_PRICES[input_mint]
                    return {
                        "status": "success",
                        "demo_message": f"Демо-своп (продажа): {output_amount} токенов ({input_mint[:6]}...{input_mint[-6:]}) -> {input_amount_sol} SOL"
                    }
                raise Exception("Недостаточно токенов в демо-кошельке для продажи")

        if action == "BUY":
            PURCHASE_PRICES[output_mint] = input_amount_sol / output_amount if output_amount > 0 else 0
        else:
            if input_mint in PURCHASE_PRICES:
                del PURCHASE_PRICES[input_mint]
                
        return {
            "status": "success",
            "tx_hash": result.get("txHash", "unknown"),
            "outAmount": output_amount,
            "inputAmount": input_amount_sol
        }

    except Exception as e:
        logger.error(f"Ошибка выполнения свопа через PumpPortal: {str(e)}")
        raise Exception(f"Ошибка выполнения свопа через PumpPortal: {str(e)}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def swap_on_gmgn(wallet: Keypair, input_mint: str, output_mint: str, amount: int, max_retries=3, retry_delay=5) -> dict:
    """Выполняет своп через GMGN.ai API"""
    GMGN_API_HOST = "https://gmgn.ai"
    slippage = 0.5
    from_address = str(wallet.pubkey())

    for attempt in range(max_retries):
        try:
            logger.info(f"Попытка свопа через GMGN.ai (попытка {attempt + 1}/{max_retries})")
            
            # Получаем маршрут для свопа
            quote_url = f"{GMGN_API_HOST}/defi/router/v1/sol/tx/get_swap_route?token_in_address={input_mint}&token_out_address={output_mint}&in_amount={amount}&from_address={from_address}&slippage={slippage}"
            response = requests.get(quote_url, timeout=15)
            response.raise_for_status()
            route = response.json()
            
            if route["code"] != 0:
                if "insufficient account balance" in route["msg"] and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise Exception(f"Ошибка получения маршрута: {route['msg']}")

            quote = route["data"]["quote"]
            raw_tx = route["data"]["raw_tx"]
            input_amount_sol = int(quote["inAmount"]) / 1_000_000_000
            output_amount = int(quote["outAmount"]) / 1_000_000_000

            if config.DEMO_MODE:
                if input_mint == "So11111111111111111111111111111111111111112":
                    if DEMO_WALLET["SOL"] >= input_amount_sol:
                        DEMO_WALLET["SOL"] -= input_amount_sol
                        DEMO_WALLET["tokens"][output_mint] = DEMO_WALLET["tokens"].get(output_mint, 0.0) + output_amount
                        PURCHASE_PRICES[output_mint] = input_amount_sol / output_amount
                        return {
                            "status": "success",
                            "demo_message": f"Демо-своп (покупка): {input_amount_sol} SOL -> {output_amount} токенов ({output_mint[:6]}...{output_mint[-6:]})"
                        }
                    raise Exception("Недостаточно SOL в демо-кошельке")
                else:
                    token_balance = DEMO_WALLET["tokens"].get(input_mint, 0.0)
                    if token_balance >= output_amount:
                        DEMO_WALLET["tokens"][input_mint] -= output_amount
                        DEMO_WALLET["SOL"] += input_amount_sol
                        if DEMO_WALLET["tokens"][input_mint] <= 0:
                            del DEMO_WALLET["tokens"][input_mint]
                            if input_mint in PURCHASE_PRICES:
                                del PURCHASE_PRICES[input_mint]
                        return {
                            "status": "success",
                            "demo_message": f"Демо-своп (продажа): {output_amount} токенов ({input_mint[:6]}...{input_mint[-6:]}) -> {input_amount_sol} SOL"
                        }
                    raise Exception("Недостаточно токенов в демо-кошельке для продажи")

            # Подписываем и отправляем транзакцию для реального режима
            swap_transaction_buf = base64.b64decode(raw_tx["swapTransaction"])
            transaction = VersionedTransaction.deserialize(swap_transaction_buf)
            transaction.sign([wallet])
            signed_tx = base64.b64encode(transaction.serialize()).decode("utf-8")

            submit_url = f"{GMGN_API_HOST}/defi/router/v1/sol/tx/submit_signed_transaction"
            submit_response = requests.post(
                submit_url,
                headers={"content-type": "application/json"},
                json={"signed_tx": signed_tx},
                timeout=15
            )
            submit_response.raise_for_status()
            submit_result = submit_response.json()
            
            if submit_result["code"] != 0:
                raise Exception(f"Ошибка отправки транзакции: {submit_result['msg']}")

            # Проверяем статус транзакции
            tx_hash = submit_result["data"]["hash"]
            last_valid_block_height = raw_tx["lastValidBlockHeight"]
            status_url = f"{GMGN_API_HOST}/defi/router/v1/sol/tx/get_transaction_status?hash={tx_hash}&last_valid_height={last_valid_block_height}"
            
            start_time = time.time()
            while time.time() - start_time < 60:
                try:
                    status_response = requests.get(status_url, timeout=5)
                    status_response.raise_for_status()
                    status = status_response.json()
                    
                    if status["code"] != 0:
                        raise Exception(f"Ошибка проверки статуса: {status['msg']}")
                    
                    if status["data"]["success"]:
                        if input_mint == "So11111111111111111111111111111111111111112":
                            PURCHASE_PRICES[output_mint] = input_amount_sol / output_amount
                        else:
                            if input_mint in PURCHASE_PRICES:
                                del PURCHASE_PRICES[input_mint]
                        return {
                            "status": "success",
                            "tx_hash": tx_hash,
                            "outAmount": output_amount
                        }
                    
                    if status["data"]["expired"]:
                        raise Exception("Транзакция истекла")
                    
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Ошибка проверки статуса: {str(e)}")
                    time.sleep(1)
                    continue

            raise Exception("Таймаут проверки статуса транзакции")

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            error_message = f"Ошибка выполнения свопа: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_message += f" Ответ сервера: {e.response.text}"
            logger.error(error_message)
            raise Exception(error_message)

    logger.error(f"Не удалось выполнить своп после {max_retries} попыток")
    raise Exception(f"Не удалось выполнить своп после {max_retries} попыток")

def swap_tokens(wallet: Keypair, input_mint: str, output_mint: str, amount: int, max_retries=3, retry_delay=5) -> dict:
    """
    Основная функция для выполнения свопа.
    """
    try:
        if config.DEMO_MODE:
            amount_in_sol = amount / 1_000_000_000
            return demo_buy_token(output_mint, amount_in_sol)

        # Для токенов на Pump.fun сначала пробуем PumpPortal
        if output_mint.lower().endswith("pump"):
            try:
                return swap_on_pump_fun(wallet, input_mint, output_mint, amount)
            except Exception as e:
                logger.warning(f"Ошибка при использовании Pump.fun: {str(e)}. Переходим к GMGN.ai.")
                return swap_on_gmgn(wallet, input_mint, output_mint, amount)
        else:
            return swap_on_gmgn(wallet, input_mint, output_mint, amount)
    except Exception as e:
        logger.error(f"Ошибка выполнения свопа: {str(e)}")
        raise Exception(f"Ошибка выполнения свопа: {str(e)}")

def sell_tokens(wallet: Keypair, token_mint: str, amount: int, profit_target: float, sell_percentage: float = 1.0, max_retries=3, retry_delay=5) -> dict:
    """Функция для продажи токенов"""
    if config.DEMO_MODE:
        return demo_sell_token(token_mint, profit_target, sell_percentage)

    current_price = get_current_price(token_mint, wallet)
    if current_price == 0.0:
        return {
            "status": "error",
            "message": "Не удалось получить текущую цену токена"
        }

    purchase_price = PURCHASE_PRICES.get(token_mint, 0.0)
    if purchase_price == 0.0:
        return {
            "status": "error",
            "message": "Цена покупки неизвестна, невозможно рассчитать прибыль"
        }

    profit_ratio = current_price / purchase_price
    if profit_ratio < profit_target:
        return {
            "status": "waiting",
            "message": f"Текущая прибыль {profit_ratio:.2f}x, ждём достижения {profit_target}x"
        }

    try:
        # Для токенов на Pump.fun сначала пробуем PumpPortal
        if token_mint.lower().endswith("pump"):
            try:
                result = swap_on_pump_fun(wallet, token_mint, "So11111111111111111111111111111111111111112", amount, action="SELL")
                send_notification(f"Sold {token_mint[:6]}...{token_mint[-6:]} with profit {profit_ratio:.2f}x")
                return {
                    "status": "sold",
                    "result": result
                }
            except Exception as e:
                logger.warning(f"Не удалось продать через PumpPortal: {str(e)}. Пробуем GMGN.ai API...")

        # Основной вариант через GMGN.ai
        result = swap_on_gmgn(wallet, token_mint, "So11111111111111111111111111111111111111112", amount, max_retries, retry_delay)
        send_notification(f"Sold {token_mint[:6]}...{token_mint[-6:]} with profit {profit_ratio:.2f}x")
        return {
            "status": "sold",
            "result": result
        }
    except Exception as e:
        logger.error(f"Не удалось выполнить продажу токена {token_mint[:6]}...{token_mint[-6:]}: {str(e)}")
        return {
            "status": "error",
            "message": f"Не удалось выполнить продажу: {str(e)}"
        }

def send_notification(message: str):
    """Отправляет уведомление в Telegram"""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Токен бота или chat ID не установлены. Уведомление пропущено.")
        return
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        response.raise_for_status()
        logger.info(f"Уведомление отправлено: {message}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление в Telegram: {e}")

def format_price(price):
    """Форматирует цену для отображения."""
    if price == 0:
        return "N/A"
    elif price < 0.001:
        exponent = int(abs(math.log10(price)))
        mantissa = price * (10**exponent)
        return f"{mantissa:.2f}e-{exponent}"
    else:
        return f"${price:.4f}"

def format_profit(profit_ratio):
    """Форматирует прибыль для отображения."""
    if profit_ratio >= 1000:
        return f"{profit_ratio / 1000:.1f}Kx"
    elif profit_ratio >= 100:
        return f"{profit_ratio:.0f}x"
    elif profit_ratio >= 10:
        return f"{profit_ratio:.1f}x"
    else:
        return f"{profit_ratio:.2f}x"

if __name__ == "__main__":
    wallet = load_wallet()
    print(f"Публичный ключ: {wallet.pubkey()}")
    print(f"Баланс SOL: {check_balance(wallet)}")

    token_mint = "6NUHnmB1vvM6byB2sCYAty6f9GGtvn1Yin6QoQimpump"
    amount = 100000000  # 0.1 SOL в lamports

    buy_result = swap_tokens(wallet, "So11111111111111111111111111111111111111112", token_mint, amount)
    print(f"Результат покупки: {buy_result}")

    profit_target = 2.0  # Целевая прибыль 2x
    for _ in range(5):  # Проверяем 5 раз с интервалом 5 минут
        time.sleep(300)  # 5 минут
        sell_result = sell_tokens(wallet, token_mint, amount, profit_target)
        print(f"Результат проверки: {sell_result}")
        if sell_result["status"] == "sold":
            break
