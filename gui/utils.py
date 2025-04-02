# gui/utils.py
import logging

def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    logging.info(f"[{timestamp}] {message}")
