# gui/settings_tab.py
import tkinter as tk
from tkinter import ttk

def create_settings_tab(notebook, app):
    settings_tab = ttk.Frame(notebook)
    notebook.add(settings_tab, text="Настройки")

    # Прокрутка
    canvas = tk.Canvas(settings_tab)
    scrollbar = ttk.Scrollbar(settings_tab, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Настройки сумм
    amounts_frame = ttk.LabelFrame(scrollable_frame, text="Суммы для сигналов (SOL)")
    amounts_frame.pack(pady=5, fill=tk.X, padx=5)
    settings = [
        ("Уверенный сигнал:", "confident_amount", "0.2"),
        ("Рискованный сигнал:", "risky_amount", "0.1"),
        ("Отложенный сигнал:", "pending_amount", "0.15")
    ]
    for i, (label, attr, default) in enumerate(settings):
        ttk.Label(amounts_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
        entry = ttk.Entry(amounts_frame)
        entry.insert(0, default)
        entry.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
        setattr(app, attr, entry)

    # Настройки торговли
    trade_frame = ttk.LabelFrame(scrollable_frame, text="Параметры торговли")
    trade_frame.pack(pady=5, fill=tk.X, padx=5)
    trade_settings = [
        ("Тейк-профит (например, 2 для 200% прибыли):", "profit_target_entry", "2.0"),
        ("Стоп-лосс (% убытка, например, 50 для 50%):", "stop_loss_entry", "50"),
        ("Процент продажи при достижении цели (%):", "sell_percentage_entry", "100")
    ]
    for i, (label, attr, default) in enumerate(trade_settings):
        ttk.Label(trade_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
        entry = ttk.Entry(trade_frame)
        entry.insert(0, default)
        entry.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
        setattr(app, attr, entry)

    return settings_tab
