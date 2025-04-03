import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
from telethon import TelegramClient
import config
import parser
from trading import (
    load_wallet,
    check_balance,
    swap_tokens,
    check_token_balance,
    sell_tokens,
    get_current_price,
    DEMO_WALLET,
    PURCHASE_PRICES,
    get_sol_price_in_usdt,
)
import json
import os
from datetime import datetime
import logging
import math

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Crypto Trading Bot")
        self.profit_monitoring = False  # Флаг мониторинга прибыли
        self.monitoring = False  # Флаг мониторинга Telegram
        self.loop = asyncio.get_event_loop()

        # Инициализация полей для настроек
        self.confident_amount = None
        self.risky_amount = None
        self.pending_amount = None
        self.profit_target_entry = None
        self.stop_loss_entry = None
        self.sell_percentage_entry = None

        self.setup_ui()
        self.setup_event_handlers()
        self.initialize_data()

    def initialize_data(self):
        """Initialize application data."""
        try:
            self.wallet = load_wallet()
            if not config.DEMO_MODE:
                self.log(f"Wallet loaded: {self.wallet.pubkey()}")
            else:
                self.log("Demo mode activated. Using virtual wallet.")

            balance = check_balance(self.wallet)
            self.log(f"SOL balance: {balance:.4f}")
        except Exception as e:
            self.show_error(f"Initialization error: {str(e)}")

    def setup_ui(self):
        """Setup main UI components."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, expand=True, fill="both")

        self.create_main_tab()
        self.create_settings_tab()
        self.create_portfolio_tab()

        # Logging area
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def create_main_tab(self):
        """Create the main tab."""
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main")

        input_frame = ttk.LabelFrame(self.main_tab, text="Token Swap")
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

        button_frame = ttk.Frame(self.main_tab)
        button_frame.pack(pady=5, fill=tk.X, padx=5)

        self.execute_swap_button = ttk.Button(button_frame, text="Execute Swap", command=self.execute_swap)
        self.execute_swap_button.pack(side=tk.LEFT, padx=5)

        self.swap_from_clipboard_button = ttk.Button(button_frame, text="Swap from Clipboard", command=self.swap_from_clipboard)
        self.swap_from_clipboard_button.pack(side=tk.LEFT, padx=5)

        self.start_monitoring_button = ttk.Button(button_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_monitoring_button.pack(side=tk.LEFT, padx=5)

    def create_settings_tab(self):
        """Создает вкладку 'Настройки'."""
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Настройки")

        # Настройка сумм для сигналов
        amounts_frame = ttk.LabelFrame(self.settings_tab, text="Суммы для сигналов")
        amounts_frame.pack(pady=5, fill=tk.X, padx=5)

        settings = [
            ("Уверенный сигнал:", "confident_amount", "0.2"),
            ("Рискованный сигнал:", "risky_amount", "0.1"),
            ("Отложенный сигнал:", "pending_amount", "0.15"),
        ]

        for i, (label, attr, default) in enumerate(settings):
            ttk.Label(amounts_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            entry = ttk.Entry(amounts_frame)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
            setattr(self, attr, entry)  # Привязываем виджет к атрибуту объекта

        # Настройки торговли
        trade_frame = ttk.LabelFrame(self.settings_tab, text="Параметры торговли")
        trade_frame.pack(pady=5, fill=tk.X, padx=5)

        trade_settings = [
            ("Целевая прибыль (x):", "profit_target_entry", "2.0"),
            ("Стоп-лосс (%):", "stop_loss_entry", "50"),
            ("Процент продажи (%):", "sell_percentage_entry", "100"),
        ]

        for i, (label, attr, default) in enumerate(trade_settings):
            ttk.Label(trade_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            entry = ttk.Entry(trade_frame)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
            setattr(self, attr, entry)  # Привязываем виджет к атрибуту объекта

        # Режим работы (демо/реальный)
        mode_frame = ttk.Frame(self.settings_tab)
        mode_frame.pack(pady=5, fill=tk.X, padx=5)

        ttk.Label(mode_frame, text="Режим работы:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.mode_var = tk.BooleanVar(value=config.DEMO_MODE)
        self.mode_check = ttk.Checkbutton(mode_frame, variable=self.mode_var, command=self.toggle_mode)
        self.mode_check.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        self.mode_label = ttk.Label(mode_frame, text="Режим: Демо" if config.DEMO_MODE else "Режим: Реальный")
        self.mode_label.grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)

        # Load saved settings
        self.load_settings()

    def create_portfolio_tab(self):
        """Create the portfolio tab."""
        self.portfolio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_tab, text="Portfolio")

        sol_frame = ttk.Frame(self.portfolio_tab)
        sol_frame.pack(fill=tk.X, padx=5, pady=5)
        self.sol_balance_label = ttk.Label(sol_frame, text="SOL: 0.0", font=("Helvetica", 10, "bold"))
        self.sol_balance_label.pack(side=tk.LEFT)
        self.last_update_label = ttk.Label(sol_frame, text="Last update: -")
        self.last_update_label.pack(side=tk.RIGHT)

        self.portfolio_tree = ttk.Treeview(
            self.portfolio_tab,
            columns=("token", "amount", "price", "value", "profit"),
            show="headings",
            height=15,
        )

        self.portfolio_tree.heading("token", text="Token")
        self.portfolio_tree.heading("amount", text="Amount")
        self.portfolio_tree.heading("price", text="Price (USDT)")
        self.portfolio_tree.heading("value", text="Value (USDT)")
        self.portfolio_tree.heading("profit", text="Profit")

        self.portfolio_tree.column("token", width=150)
        self.portfolio_tree.column("amount", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("price", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("value", width=100, anchor=tk.CENTER)
        self.portfolio_tree.column("profit", width=100, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(self.portfolio_tab, orient=tk.VERTICAL, command=self.portfolio_tree.yview)
        self.portfolio_tree.configure(yscroll=scrollbar.set)
        self.portfolio_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        update_button = ttk.Button(self.portfolio_tab, text="Update", command=self.update_portfolio)
        update_button.pack(pady=5)

    def setup_event_handlers(self):
        """Setup event handlers."""
        pass

    def save_demo_data(self):
        """Save demo data to file."""
        if config.DEMO_MODE:
            try:
                data = {
                    "DEMO_WALLET": DEMO_WALLET,
                    "PURCHASE_PRICES": PURCHASE_PRICES,
                    "settings": {
                        "confident_amount": self.confident_amount.get(),
                        "risky_amount": self.risky_amount.get(),
                        "pending_amount": self.pending_amount.get(),
                        "profit_target": self.profit_target_entry.get(),
                        "stop_loss": self.stop_loss_entry.get(),
                        "sell_percentage": self.sell_percentage_entry.get(),
                    },
                }
                with open("demo_data.json", "w") as f:
                    json.dump(data, f, indent=4)
                self.log(f"Demo data saved: {DEMO_WALLET}")
            except Exception as e:
                self.show_error(f"Error saving demo data: {str(e)}")

    def load_settings(self):
        """Load settings from file."""
        if config.DEMO_MODE and os.path.exists("demo_data.json"):
            try:
                with open("demo_data.json", "r") as f:
                    data = json.load(f)
                settings = data.get("settings", {})
                self.confident_amount.delete(0, tk.END)
                self.confident_amount.insert(0, settings.get("confident_amount", "0.2"))
                self.risky_amount.delete(0, tk.END)
                self.risky_amount.insert(0, settings.get("risky_amount", "0.1"))
                self.pending_amount.delete(0, tk.END)
                self.pending_amount.insert(0, settings.get("pending_amount", "0.05"))
                self.profit_target_entry.delete(0, tk.END)
                self.profit_target_entry.insert(0, settings.get("profit_target", "2.0"))
                self.stop_loss_entry.delete(0, tk.END)
                self.stop_loss_entry.insert(0, settings.get("stop_loss", "0.5"))
                self.sell_percentage_entry.delete(0, tk.END)
                self.sell_percentage_entry.insert(0, settings.get("sell_percentage", "100"))
                self.log("Settings loaded from file.")
            except Exception as e:
                self.show_error(f"Error loading settings: {str(e)}")

    def on_closing(self):
        """Handle window closing event."""
        try:
            self.save_demo_data()
            self.monitoring = False
            self.profit_monitoring = False
            self.root.destroy()
        except Exception as e:
            self.show_error(f"Error during closing: {str(e)}")

    def log(self, message: str):
        """Log messages to the interface."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        logger.info(message)

    def show_error(self, message: str):
        """Display error message."""
        messagebox.showerror("Error", message)
        logger.error(message)
        self.log(f"ERROR: {message}")

    def toggle_mode(self):
        """Toggle between demo and real mode."""
        config.DEMO_MODE = self.mode_var.get()
        self.mode_label.config(text="Режим: Демо" if config.DEMO_MODE else "Режим: Реальный")
        self.log(f"Mode changed: {'Demo' if config.DEMO_MODE else 'Real'}")
        self.log(f"SOL balance: {check_balance(self.wallet)}")

    def execute_swap(self, signal=None):
        """Execute token swap based on signal or user input."""
        input_mint = self.input_mint_entry.get().strip() or "So11111111111111111111111111111111111111112"
        output_mint = self.output_mint_entry.get().strip()
        amount_str = self.amount_entry.get().strip()

        if signal:
            output_mint = signal["contract_address"]
            amount_str = signal.get("amount", "0.1")  # Default value

        if not output_mint or not amount_str:
            self.show_error("Error: All fields must be filled.")
            return

        try:
            amount = float(amount_str) * 1_000_000_000
            if amount <= 0:
                self.show_error("Error: Amount must be greater than 0.")
                return
        except ValueError:
            self.show_error("Error: Invalid amount value.")
            return

        try:
            quote = swap_tokens(self.wallet, input_mint, output_mint, int(amount))
            if config.DEMO_MODE:
                self.log(quote.get("demo_message", "Demo swap executed"))
                self.log(f"Demo SOL balance: {check_balance(self.wallet)}")
                self.log(f"Demo {output_mint} balance: {check_token_balance(self.wallet, output_mint)}")
            else:
                self.log(f"Swap executed. Transaction hash: {quote['tx_hash']}")
            self.update_portfolio()
        except Exception as e:
            self.show_error(f"Swap error: {str(e)}")

    def swap_from_clipboard(self):
        """Execute swap based on clipboard data."""
        try:
            clipboard_text = self.root.clipboard_get()
            self.log(f"Clipboard text: {clipboard_text}")
            signal = parser.parse_message(clipboard_text)
            if "buy" in signal["recommendations"] and signal["contract_address"]:
                self.execute_swap(signal)
            else:
                self.log("Error: Signal not recognized or not for buying.")
        except tk.TclError:
            self.show_error("Error: Failed to get clipboard data.")

    def start_monitoring(self):
        """Start Telegram channel monitoring."""
        if not self.monitoring:
            self.monitoring = True
            self.loop.create_task(self.monitor_telegram())
            self.log("Telegram channel monitoring started.")
        else:
            self.log("Monitoring is already running.")

    async def monitor_telegram(self):
        """Asynchronous Telegram channel monitoring."""
        telegram_client = TelegramClient('session', config.API_ID, config.API_HASH)
        await telegram_client.start()
        self.log(f"Monitoring channel {config.TELEGRAM_CHANNEL} started.")

        while self.monitoring:
            try:
                async for message in telegram_client.iter_messages(config.TELEGRAM_CHANNEL, limit=1):
                    if message.text:
                        signal = parser.parse_message(message.text)
                        if "buy" in signal["recommendations"] and signal["contract_address"]:
                            self.execute_swap(signal)
            except Exception as e:
                self.show_error(f"Telegram monitoring error: {str(e)}")
            await asyncio.sleep(5)

    def update_portfolio(self):
        """Update portfolio display using Treeview."""
        try:
            # Clear current data
            for item in self.portfolio_tree.get_children():
                self.portfolio_tree.delete(item)

            # Update SOL info
            sol_balance = check_balance(self.wallet)
            sol_price_usdt = get_sol_price_in_usdt()
            self.sol_balance_label.config(text=f"SOL: {sol_balance:.4f} (${sol_balance * sol_price_usdt:.2f})")
            self.last_update_label.config(text=f"Last update: {datetime.now().strftime('%H:%M:%S')}")

            # Update token data
            tokens = DEMO_WALLET["tokens"].items() if config.DEMO_MODE else []

            for token_mint, amount in tokens:
                current_price = get_current_price(token_mint, self.wallet)
                if current_price == 0:
                    continue

                value_sol = amount * current_price
                purchase_price = PURCHASE_PRICES.get(token_mint, 0)
                profit_ratio = current_price / purchase_price if purchase_price > 0 else 0.0

                formatted_amount = f"{amount:.2f}"
                formatted_price = self.format_price(current_price)
                formatted_value = f"${value_sol:.2f}" if value_sol > 0 else "N/A"
                formatted_profit = self.format_profit(profit_ratio)

                self.portfolio_tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"{token_mint[:4]}...{token_mint[-4:]}",
                        formatted_amount,
                        formatted_price,
                        formatted_value,
                        formatted_profit,
                    ),
                )
        except Exception as e:
            self.show_error(f"Portfolio update error: {str(e)}")

    def format_price(self, price):
        """Format price for display."""
        if price == 0:
            return "N/A"
        elif price < 0.001:
            exponent = int(abs(math.log10(price)))
            mantissa = price * (10**exponent)
            return f"{mantissa:.2f}e-{exponent}"
        else:
            return f"${price:.4f}"

    def format_profit(self, profit_ratio):
        """Format profit for display."""
        if profit_ratio >= 1000:
            return f"{profit_ratio / 1000:.1f}Kx"
        elif profit_ratio >= 100:
            return f"{profit_ratio:.0f}x"
        elif profit_ratio >= 10:
            return f"{profit_ratio:.1f}x"
        else:
            return f"{profit_ratio:.2f}x"


def main():
    root = tk.Tk()
    app = TradingBotGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
