# gui/main_tab.py (фрагмент)
import tkinter as tk
# ... другие импорты

class MainTab(tk.Frame):
    def __init__(self, parent_notebook, app_controller):
        super().__init__(parent_notebook)
        self.app = app_controller # Ссылка на основной класс приложения

        # ... создание виджетов (entries, buttons, log_area) ...

        # Привязка кнопок к методам контроллера app
        self.execute_button = tk.Button(self, text="Execute Swap", command=self.app.execute_swap_from_gui)
        self.execute_button.grid(row=3, column=0, pady=5)

        self.clipboard_button = tk.Button(self, text="Swap from Clipboard", command=self.app.swap_from_clipboard)
        self.clipboard_button.grid(row=3, column=1, pady=5)

        self.monitor_button = tk.Button(self, text="Start Monitoring", command=self.toggle_monitoring)
        self.monitor_button.grid(row=4, column=0, pady=5)

        # ... остальные виджеты ...

    def toggle_monitoring(self):
        # Логика переключения теперь в app
        if self.app.telegram_monitoring_active:
             self.app.stop_telegram_monitoring()
        else:
             self.app.start_telegram_monitoring()
        # Мониторинг прибыли может управляться отдельно
        # if self.app.profit_monitoring_active:
        #      self.app.stop_profit_monitoring()
        # else:
        #      self.app.start_profit_monitoring()


    def update_monitoring_button_state(self, is_active):
        """Обновляет текст кнопки мониторинга."""
        new_text = "Stop Monitoring" if is_active else "Start Monitoring"
        if self.monitor_button.winfo_exists(): # Проверка, существует ли виджет
             self.monitor_button.config(text=new_text)

    def set_swap_buttons_state(self, state):
         """Включает/выключает кнопки свопа."""
         if self.execute_button.winfo_exists():
             self.execute_button.config(state=state)
         if self.clipboard_button.winfo_exists():
             self.clipboard_button.config(state=state)

    def update_log(self, message):
        """Добавляет сообщение в текстовое поле лога."""
        if self.log_area.winfo_exists():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.config(state=tk.DISABLED)
            self.log_area.see(tk.END) # Прокрутка вниз

    def get_mode(self):
         """Возвращает выбранный режим (Демо/Реал)."""
         # Ваша реализация получения режима из Radiobutton или другого виджета
         # return self.mode_var.get() 
         return "Демо" # Заглушка

    # ... другие методы ...
