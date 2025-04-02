# trading/monitor.py
import time
import logging
import queue # Добавить импорт
import threading # Добавить импорт
# ... другие ваши импорты (api, wallet и т.д.) ...
from trading.swap import sell_tokens # Предполагаем, что эта функция продает токен

def profit_monitoring_task(config, gui_queue, stop_event, get_profit_target_func, get_demo_mode_func):
    """
    Фоновая задача для мониторинга прибыли и автоматической продажи.

    Args:
        config: Конфигурация приложения.
        gui_queue: Очередь для отправки сообщений в GUI.
        stop_event: threading.Event для сигнала остановки.
        get_profit_target_func: Функция для получения целевой прибыли из GUI настроек.
        get_demo_mode_func: Функция для получения текущего режима (Демо/Реал) из GUI.
    """
    logging.info("Поток мониторинга прибыли запущен.")
    
    while not stop_event.is_set():
        try:
            demo_mode = get_demo_mode_func()
            profit_target = get_profit_target_func()
            
            # 1. Получить текущий портфель (токены и цены покупки)
            # Эта логика должна быть здесь или в wallet.py
            # portfolio_tokens = get_current_portfolio(demo_mode) # Ваша функция
            portfolio_tokens = _get_monitor_portfolio_data(demo_mode) # Используем временную заглушку

            if not portfolio_tokens:
                # Если портфель пуст, просто ждем
                time.sleep(config.get('monitoring_interval', 60)) # Интервал из конфига или по умолчанию
                continue

            # 2. Получить текущие цены для токенов в портфеле
            token_addresses = list(portfolio_tokens.keys())
            # current_prices = get_current_prices(token_addresses, config) # Ваша функция API

            # 3. Проверить каждый токен на достижение цели
            for address, data in portfolio_tokens.items():
                if stop_event.is_set(): # Проверяем флаг остановки внутри цикла
                     break 
                 
                # current_price = current_prices.get(address)
                current_price = data.get('current_price_dummy', 0) # Используем заглушку цены
                purchase_price = data.get('purchase_price')
                amount = data.get('amount')

                if current_price is not None and purchase_price is not None and purchase_price > 0 and amount > 0:
                    profit_multiplier = current_price / purchase_price
                    
                    # Сообщение для лога или обновления портфеля в GUI
                    profit_update_msg = f"Токен {address[:6]}..: тек. цена {current_price:.6f}, покупка {purchase_price:.6f}, профит {profit_multiplier:.2f}x"
                    # Отправляем обновление в GUI (возможно, стоит отправлять реже)
                    # gui_queue.put(('log', profit_update_msg)) 

                    if profit_multiplier >= profit_target:
                        log_msg = f"Цель {profit_target:.2f}x достигнута для {address} (тек. {profit_multiplier:.2f}x). Продаю..."
                        logging.info(log_msg)
                        gui_queue.put(('log', log_msg))

                        # Запускаем продажу (должна быть неблокирующей или в своем потоке, если долгая)
                        # ВАЖНО: sell_tokens не должна блокировать этот поток надолго!
                        # Если sell_tokens сама по себе долгая (API вызовы), ее тоже нужно запускать в отдельном потоке.
                        # Пока предполагаем, что она относительно быстрая или сама запускает поток.
                        try:
                             sell_result = sell_tokens(address, amount, demo_mode, config) # Ваша функция продажи
                             gui_queue.put(('log', f"Результат продажи {address[:6]}..: {sell_result}"))
                             # После продажи стоит обновить данные портфеля в GUI
                             gui_queue.put(('trigger_portfolio_update', None)) # Сигнал для App обновить портфель
                        except Exception as e:
                             err_msg = f"Ошибка при продаже {address[:6]}..: {e}"
                             logging.exception(err_msg)
                             gui_queue.put(('log', err_msg))
                             gui_queue.put(('show_error', 'Ошибка авто-продажи', err_msg))

            if stop_event.is_set(): # Проверяем еще раз перед сном
                 break

            # Пауза перед следующей проверкой
            sleep_interval = config.get('monitoring_interval', 60) 
            # Умный сон: спим короткими интервалами, чтобы быстрее реагировать на stop_event
            for _ in range(sleep_interval):
                 if stop_event.is_set():
                      break
                 time.sleep(1)
                 
        except Exception as e:
            logging.exception("Ошибка в цикле мониторинга прибыли:")
            gui_queue.put(('log', f"Критическая ошибка в мониторинге прибыли: {e}"))
            # Пауза перед повторной попыткой в случае серьезной ошибки
            for _ in range(30): 
                 if stop_event.is_set(): break
                 time.sleep(1)

    logging.info("Поток мониторинга прибыли завершен.")


# Временная заглушка для получения данных портфеля для мониторинга
# Замените ее реальной логикой (вероятно, из wallet.py)
from trading.wallet import DEMO_WALLET 
def _get_monitor_portfolio_data(demo_mode):
     if demo_mode:
         # Добавим заглушку текущей цены для тестирования
         # В реальности цена должна браться из API
         import random
         tokens = {}
         for addr, data in DEMO_WALLET['tokens'].items():
              if data['purchase_price'] > 0:
                   # Симулируем изменение цены для теста
                   simulated_price = data['purchase_price'] * random.uniform(0.8, 2.5) 
                   tokens[addr] = {**data, 'current_price_dummy': simulated_price}
              else:
                   tokens[addr] = {**data, 'current_price_dummy': 0}
         return tokens

     else:
         # Логика для реального режима
         return {}
