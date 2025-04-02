# gui/portfolio_tab.py
import tkinter as tk
from tkinter import ttk

def create_portfolio_tab(notebook, app):
    portfolio_tab = ttk.Frame(notebook)
    notebook.add(portfolio_tab, text="Портфель")

    # Информация о SOL
    sol_frame = ttk.Frame(portfolio_tab)
    sol_frame.pack(fill=tk.X, padx=5, pady=5)
    sol_balance_label = ttk.Label(sol_frame, text="SOL: 0.0", font=('Helvetica', 10, 'bold'))
    sol_balance_label.pack(side=tk.LEFT)
    last_update_label = ttk.Label(sol_frame, text="Последнее обновление: -")
    last_update_label.pack(side=tk.RIGHT)

    # Таблица портфеля
    portfolio_tree = ttk.Treeview(
        portfolio_tab,
        columns=("token", "amount", "price", "value", "profit"),
        show="headings",
        height=15
    )

    # Настройка колонок
    columns = [
        ("token", "Токен", 120, tk.W),
        ("amount", "Количество", 100, tk.E),
        ("price", "Цена (SOL)", 120, tk.E),
        ("value", "Стоимость (SOL)", 120, tk.E),
        ("profit", "Прибыль", 100, tk.E)
    ]
    for col_id, heading, width, anchor in columns:
        portfolio_tree.heading(col_id, text=heading)
        portfolio_tree.column(col_id, width=width, anchor=anchor)

    # Прокрутка
    scrollbar = ttk.Scrollbar(portfolio_tab, orient="vertical", command=portfolio_tree.yview)
    portfolio_tree.configure(yscrollcommand=scrollbar.set)
    portfolio_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    return portfolio_tab
