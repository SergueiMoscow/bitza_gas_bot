"""
Фикстуры для тестирования Gas Bot
"""
import pytest
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import Database
from src.parser import MessageParser
from src.bot import GasBot


@pytest.fixture(scope='function')
def test_db():
    """
    Создает тестовую БД для каждого теста.
    После теста очищает данные и удаляет файл БД.
    """
    db = Database(db_url='sqlite:///test_gas.db')

    # Очищаем БД перед тестом
    db.clear_all_records()

    yield db

    # Очищаем после теста
    db.clear_all_records()

    # Удаляем файл БД после всех тестов
    db_file = 'test_gas.db'
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception as e:
            print(f"Warning: Could not remove test DB file: {e}")


@pytest.fixture
def parser():
    """Возвращает экземпляр парсера сообщений"""
    return MessageParser()


@pytest.fixture
def mock_update():
    """
    Создает мок объекта Update от Telegram.
    Имитирует входящее сообщение от пользователя.
    """
    update = MagicMock()

    # Настройка пользователя
    update.message.from_user.id = 12345
    update.message.from_user.first_name = "Тест"
    update.message.from_user.last_name = "Пользователь"
    update.message.from_user.username = "testuser"

    # Настройка сообщения
    update.message.message_id = 1
    update.message.date = datetime.now()
    update.message.text = ""
    update.message.chat_id = 12345

    # Мокаем асинхронные методы
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message

    return update


@pytest.fixture
def mock_context():
    """
    Создает мок объекта Context от Telegram.
    Используется для работы с ботом и отправки сообщений.
    """
    context = MagicMock()

    # Мокаем bot методы
    context.bot.send_message = AsyncMock()
    context.bot.get_chat = AsyncMock()

    # Мок для получения информации о пользователе
    mock_chat = MagicMock()
    mock_chat.first_name = "Тест"
    mock_chat.last_name = "Пользователь"
    mock_chat.username = "testuser"
    context.bot.get_chat.return_value = mock_chat

    return context


@pytest.fixture
def gas_bot(test_db, monkeypatch):
    """
    Создает экземпляр бота для тестов.
    Использует тестовую БД и моканные переменные окружения.
    """
    # Мокаем переменные окружения
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test_token_123456789')
    monkeypatch.setenv('ALLOWED_USER_IDS', '12345,67890')
    monkeypatch.setenv('ADMIN_USER_ID', '12345')
    monkeypatch.setenv('WEB_APP_DOMAIN', 'http://localhost:5000')

    # Создаем бота
    bot = GasBot()

    # Подменяем БД на тестовую
    bot.db = test_db

    return bot


@pytest.fixture
def sample_gas_records(test_db):
    """
    Создает набор тестовых записей в БД.
    Полезно для тестирования запросов и связывания записей.

    Возвращает список созданных записей:
    - records[0]: Приход 10 баллонов 27л
    - records[1]: Расход с оплатой (комната 2.01)
    - records[2]: Расход без оплаты (комната 3.05)
    - records[3]: Предоплата (комната 4.10)
    """
    session = test_db.get_session()

    from src.models import GasRecord

    records_data = [
        # 1. Приход баллонов
        {
            'message_id': 1001,
            'date': datetime(2025, 10, 1, 10, 0),
            'quantity': 10,
            'capacity': 27,
            'sender_user_id': 12345,
            'sender_name': 'Админ'
        },
        # 2. Расход с оплатой
        {
            'message_id': 1002,
            'date': datetime(2025, 10, 2, 14, 0),
            'quantity': -1,
            'capacity': 27,
            'room': '2.01',
            'amount': 1000,
            'receiver': 'Иван',
            'payment_date': datetime(2025, 10, 2, 14, 0),
            'sender_user_id': 12345,
            'sender_name': 'Админ'
        },
        # 3. Расход без оплаты (долг)
        {
            'message_id': 1003,
            'date': datetime(2025, 10, 3, 15, 0),
            'quantity': -1,
            'capacity': 27,
            'room': '3.05',
            'sender_user_id': 12345,
            'sender_name': 'Админ'
        },
        # 4. Предоплата (висящая)
        {
            'message_id': 1004,
            'date': datetime(2025, 10, 4, 16, 0),
            'room': '4.10',
            'amount': 1000,
            'receiver': 'Мария',
            'payment_date': datetime(2025, 10, 4, 16, 0),
            'sender_user_id': 12345,
            'sender_name': 'Админ'
        }
    ]

    records = []
    for data in records_data:
        record = GasRecord(**data)
        session.add(record)
        records.append(record)

    session.commit()

    # Обновляем объекты после коммита
    for record in records:
        session.refresh(record)

    session.close()

    return records


@pytest.fixture
def clean_test_db():
    """
    Очищает все тестовые файлы БД перед запуском.
    Полезно для начала тестов с чистого листа.
    """
    import glob

    # Удаляем все тестовые БД
    test_db_files = glob.glob('test*.db*')
    for db_file in test_db_files:
        try:
            os.remove(db_file)
        except Exception as e:
            print(f"Warning: Could not remove {db_file}: {e}")

    yield

    # После тестов тоже очищаем
    test_db_files = glob.glob('test*.db*')
    for db_file in test_db_files:
        try:
            os.remove(db_file)
        except Exception as e:
            print(f"Warning: Could not remove {db_file}: {e}")


# Автоматическое использование для всех тестов
@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """
    Автоматически применяется ко всем тестам.
    Настраивает окружение для безопасного тестирования.
    """
    # Убеждаемся что используется тестовая БД
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///test_gas.db')

    # Отключаем реальные HTTP запросы
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test_token')

    yield