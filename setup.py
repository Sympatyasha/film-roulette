import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import init_database

if __name__ == "__main__":
    print("Настройка базы данных...")
    init_database()
    print("Готово!")
