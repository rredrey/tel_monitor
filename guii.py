# guii.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from datetime import datetime
import logging
import math
import threading
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Импорты необходимых функций из trading.py
from trading import (
    load_wallet,
    check_balance,
    swap_tokens,
    sell_tokens,
    get_current_price,
    DEMO_WALLET,
    PURCHASE_PRICES,
    get_sol_price_in_usdt,
    check_token_balance,
    config
)

class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Crypto Trading Bot")
        self.profit_monitoring = False  # Флаг мониторинга прибыли
        self.monitoring = False  # Флаг мониторинга Telegram
        self.setup_ui()
        self.setup_event_handlers()
        self.initialize_data()

    def setup_ui(self):
        """Настройка основного интерфейса."""
        # Основное окно
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, expand=True, fill="both")

        # Создаем вкладки
        self.create_main_tab()
        self.create_settings_tab()
        self.create_portfolio_tab()

        # Логирование
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def create_main_tab(self):
        """Создает вкладку 'Основная'."""
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Основная")

        # Поля для ввода данных
        input_frame = ttk.LabelFrame(self.main_tab, text="Покупка токенов")
        input_frame.pack(pady=5, fill=tk.X, padx=5)

        ttk.Label(input_frame, text="Input Mint (SOL):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.input_mint_entry = ttk.Entry(input_frame)
        self.input_mint_entry.insert(0, "So11111111111111111111111111111111111111112")
        self.input_mint_entry.grid(row=0, column=1, padx=5, pady=2, sticky=tk.EW)

        ttk.Label(input_frame, text="Output Mint:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.output_mint_entry = ttk.Entry(input_frame)
        self.output_mint_entry.grid(row=1, column=1, padx=5, pady=2, sticky=tk.EW)

        ttk.Label(input_frame, text="Amount (SOL):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.amount_entry = ttk.Entry(input_frame)
        self.amount_entry.grid(row=2, column=1, padx=5, pady=2, sticky=tk.EW)

        # Кнопки
        button_frame = ttk.Frame(self.main_tab)
        button_frame.pack(pady=5, fill=tk.X, padx=5)

        self.execute_swap_button = ttk.Button(button_frame, text="Execute Swap", command=self.execute_swap)
        self.execute_swap_button.pack(side=tk.LEFT, padx=5)

        self.swap_from_clipboard_button = ttk.Button(button_frame, text="Swap from Clipboard", command=self.swap_from_clipboard)
        self.swap_from_clipboard_button.pack(side=tk.LEFT, padx=5)

        self.start_monitoring_button = ttk.Button(button_frame, text="Start Monitoring", command=self.toggle_monitoring)
        self.start_monitoring_button.pack(side=tk.LEFT, padx=5)

    def create_portfolio_tab(self):
        """Создает вкладку 'Портфель'."""
        self.portfolio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_tab, text="Портфель")

        # Информация о SOL
        sol_frame = ttk.Frame(self.portfolio_tab)
        sol_frame.pack(fill=tk.X, padx=5, pady=5)
        self.sol_balance_label = ttk.Label(sol_frame, text="SOL: 0.0", font=("Helvetica", 10, "bold"))
        self.sol_balance_label.pack(side=tk.LEFT)
        self.last_update_label = ttk.Label(sol_frame, text="Последнее обновление: -")
        self.last_update_label.pack(side=tk.RIGHT)

        # Таблица портфеля
        self.portfolio_tree = ttk.Treeview(
            self.portfolio_tab,
            columns=("token", "amount", "price", "value", "profit"),
            show="headings",
            height=15,
        )

        # Настройка заголовков столбцов
        self.portfolio_tree.heading("token", text="Токен")
        self.portfolio_tree.heading("amount", text="Количество")
        self.portfolio_tree.heading("price", text="Цена (USDT)")
        self.portfolio_tree.heading("value", text="Стоимость (USDT)")
        self.portfolio_tree.heading("profit", text="Прибыль")

        # Настройка ширины столбцов
        self.portfolio_tree.column("token", width=150)
        self.portfolio_tree.column("amount", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("price", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("value", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("profit", width=100, anchor=tk.CENTER)

        # Добавление полосы прокрутки
        scrollbar = ttk.Scrollbar(self.portfolio_tab, orient=tk.VERTICAL, command=self.portfolio_tree.yview)
        self.portfolio_tree.configure(yscroll=scrollbar.set)
        self.portfolio_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопка обновления
        update_button = ttk.Button(self.portfolio_tab, text="Обновить", command=self.update_portfolio)
        update_button.pack(pady=5)

    def initialize_data(self):
        """Инициализация данных."""
        try:
            self.wallet = load_wallet()
            if not config.DEMO_MODE:
                self.log(f"Кошелёк загружен: {self.wallet.pubkey()}")
            else:
                self.log("Демо-режим активирован. Используется виртуальный кошелёк.")

            balance = check_balance(self.wallet)
            self.log(f"Баланс SOL: {balance:.4f}")
        except Exception as e:
            self.show_error(f"Ошибка инициализации данных: {str(e)}")

    def update_portfolio(self):
        """Обновляет отображение портфеля."""
        try:
            # Очищаем текущие данные
            for item in self.portfolio_tree.get_children():
                self.portfolio_tree.delete(item)

            # Получаем баланс SOL
            sol_balance = check_balance(self.wallet)
            sol_price_usdt = get_sol_price_in_usdt()
            self.sol_balance_label.config(text=f"SOL: {sol_balance:.4f} (${sol_balance * sol_price_usdt:.2f})")
            self.last_update_label.config(text=f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}")

            # Обновляем данные для токенов
            if config.DEMO_MODE:
                tokens = DEMO_WALLET["tokens"].items()
            else:
                tokens = []  # Реализуйте логику получения токенов

            for token_mint, amount in tokens:
                try:
                    # Получаем текущую цену токена
                    current_price = get_current_price(token_mint, self.wallet)
                    if current_price == 0:
                        raise ValueError(f"Не удалось получить цену для токена {token_mint}")

                    # Вычисляем стоимость токенов в SOL
                    value_sol = amount * current_price

                    # Получаем цену покупки из хранилища PURCHASE_PRICES
                    purchase_price = PURCHASE_PRICES.get(token_mint, 0)
                    if purchase_price > 0:
                        profit_ratio = current_price / purchase_price
                    else:
                        profit_ratio = 0.0

                    # Форматируем данные для отображения
                    formatted_amount = f"{amount:.2f}"  # Округляем количество до двух знаков
                    formatted_price = self.format_price(current_price)  # Форматируем цену
                    formatted_value = f"${value_sol:.2f}" if value_sol > 0 else "N/A"
                    formatted_profit = self.format_profit(profit_ratio)  # Форматируем прибыль

                    # Добавляем строку в таблицу
                    self.portfolio_tree.insert(
                        "",
                        tk.END,
                        values=(
                            token_mint,  # Название токена (сокращённое)
                            formatted_amount,  # Количество
                            formatted_price,  # Цена
                            formatted_value,  # Стоимость
                            formatted_profit,  # Прибыль
                        ),
                        tags=("profit_positive" if profit_ratio >= 1 else "profit_negative"),
                    )

                    # Привязываем событие клика на название токена
                    self.portfolio_tree.tag_bind(
                        token_mint,
                        "<Button-1>",
                        lambda event, addr=token_mint: self.copy_to_clipboard(addr),
                    )

                except Exception as e:
                    logger.error(f"Ошибка при обновлении токена {token_mint}: {str(e)}")
                    continue

        except Exception as e:
            self.show_error(f"Ошибка обновления портфеля: {str(e)}")

    def copy_to_clipboard(self, text):
        """Копирует текст в буфер обмена."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"Скопировано в буфер обмена: {text}")

    def format_price(self, price):
        """Форматирует цену для отображения."""
        if price == 0:
            return "N/A"
        elif price < 0.001:
            # Если цена меньше 0.001, используем научную запись
            exponent = int(abs(math.log10(price)))
            mantissa = price * (10**exponent)
            return f"{mantissa:.2f}e-{exponent}"
        else:
            return f"${price:.4f}"

    def format_profit(self, profit_ratio):
        """Форматирует прибыль для отображения."""
        if profit_ratio >= 1000:
            return f"{profit_ratio / 1000:.1f}Kx"
        elif profit_ratio >= 100:
            return f"{profit_ratio:.0f}x"
        elif profit_ratio >= 10:
            return f"{profit_ratio:.1f}x"
        else:
            return f"{profit_ratio:.2f}x"

    def start_portfolio_updater(self):
        """Запускает фоновое обновление портфеля."""
        def update_loop():
            while True:
                try:
                    self.update_portfolio()
                    time.sleep(60)  # Обновляем каждые 60 секунд
                except Exception as e:
                    logger.error(f"Ошибка в фоновом обновлении портфеля: {str(e)}")
                    time.sleep(10)

        threading.Thread(target=update_loop, daemon=True).start()

    def setup_event_handlers(self):
        """Настройка обработчиков событий."""
        if hasattr(self, "update_button"):
            self.update_button.config(command=self.update_portfolio)

        if hasattr(self, "start_monitoring_button"):
            self.start_monitoring_button.config(command=self.toggle_monitoring)

        if hasattr(self, "execute_swap_button"):
            self.execute_swap_button.config(command=self.execute_swap)

        # Добавляем таймер для кнопки "Обновить"
        self.update_timer_label = ttk.Label(self.portfolio_tab, text="Обновление через: 60 сек")
        self.update_timer_label.pack(pady=5)
        self.start_update_timer()

    def start_update_timer(self):
        """Запускает таймер для кнопки 'Обновить'."""
        remaining_time = 60

        def update_timer():
            nonlocal remaining_time
            if remaining_time > 0:
                self.update_timer_label.config(text=f"Обновление через: {remaining_time} сек")
                remaining_time -= 1
                self.root.after(1000, update_timer)
            else:
                self.update_portfolio()
                remaining_time = 60  # Сброс таймера
                self.root.after(1000, update_timer)

        update_timer()

    def execute_swap(self, signal=None):
        """Выполняет своп на основе сигнала или ввода пользователя."""
        input_mint = self.input_mint_entry.get().strip() or "So11111111111111111111111111111111111111112"
        output_mint = self.output_mint_entry.get().strip()
        amount_str = self.amount_entry.get().strip()

        if not output_mint or not amount_str:
            self.show_error("Ошибка: Все поля должны быть заполнены.")
            return

        try:
            amount = float(amount_str) * 1_000_000_000
            if amount <= 0:
                self.show_error("Ошибка: Сумма должна быть больше 0.")
                return
        except ValueError:
            self.show_error("Ошибка: Некорректное значение суммы.")
            return

        try:
            quote = swap_tokens(self.wallet, input_mint, output_mint, int(amount))
            if config.DEMO_MODE:
                self.log(quote.get("demo_message", "Демо-своп выполнен"))
                self.log(f"Демо-баланс SOL: {check_balance(self.wallet)}")
                self.log(f"Демо-баланс {output_mint}: {check_token_balance(self.wallet, output_mint)}")
            else:
                self.log(f"Своп выполнен. Хэш транзакции: {quote['tx_hash']}")
            self.update_portfolio()
        except Exception as e:
            self.show_error(f"Ошибка свопа: {str(e)}")

    def log(self, message: str):
        """Логирование сообщений в интерфейсе."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        logger.info(message)

    def show_error(self, message: str):
        """Отображает ошибку."""
        messagebox.showerror("Ошибка", message)
        logger.error(message)
        self.log(f"ОШИБКА: {message}")

    def toggle_monitoring(self):
        """Переключает состояние мониторинга."""
        self.monitoring = not self.monitoring
        if self.monitoring:
            self.start_monitoring_button.config(text="Stop Monitoring")
            self.log("Мониторинг Telegram запущен")
        else:
            self.start_monitoring_button.config(text="Start Monitoring")
            self.log("Мониторинг Telegram остановлен")

    def swap_from_clipboard(self):
        """Выполняет своп на основе данных из буфера обмена."""
        try:
            clipboard_content = self.root.clipboard_get().strip()
            if not clipboard_content:
                self.show_error("Буфер обмена пуст")
                return

            # Ожидаем формат: "OutputMint Amount"
            parts = clipboard_content.split()
            if len(parts) != 2:
                self.show_error("Некорректный формат данных в буфере обмена. Ожидается: 'OutputMint Amount'")
                return

            output_mint, amount = parts
            self.output_mint_entry.delete(0, tk.END)
            self.output_mint_entry.insert(0, output_mint)
            self.amount_entry.delete(0, tk.END)
            self.amount_entry.insert(0, amount)
            self.log(f"Данные из буфера обмена: {output_mint} {amount}")
        except Exception as e:
            self.show_error(f"Ошибка при чтении из буфера обмена: {str(e)}")

    def create_settings_tab(self):
        """Создает вкладку 'Настройки'."""
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Настройки")
        # Здесь можно добавить элементы управления для настроек
        ttk.Label(self.settings_tab, text="Настройки будут добавлены здесь").pack(pady=20)


# Для запуска приложения
if __name__ == "__main__":
    root = tk.Tk()
    app = TradingBotGUI(root)
    root.mainloop()
