import pytest
from datetime import datetime
from src.database import Database

from src.models import GasRecord


class TestDatabase:
    """Тесты для класса Database"""

    def test_add_record(self, test_db):
        """Тест добавления записи в БД"""
        record_data = {
            'message_id': 1001,
            'date': datetime.now(),
            'quantity': 5,
            'capacity': 27,
            'sender_user_id': 12345,
            'sender_name': 'Test User'
        }

        record = test_db.add_record(record_data)
        assert record is not None
        assert record.id is not None
        assert record.quantity == 5

    def test_add_duplicate_message_id(self, test_db):
        """Тест добавления записи с дублирующимся message_id"""
        record_data = {
            'message_id': 1002,
            'date': datetime.now(),
            'quantity': 3,
            'capacity': 27
        }

        # Первая запись
        record1 = test_db.add_record(record_data)

        # Вторая запись с тем же message_id
        record2 = test_db.add_record(record_data)

        assert record1.id == record2.id  # Должна вернуться существующая запись

    def test_get_record_by_id(self, test_db):
        """Тест получения записи по ID"""
        record_data = {
            'message_id': 1003,
            'date': datetime.now(),
            'quantity': -1,
            'capacity': 27,
            'room': '1.01'
        }

        added_record = test_db.add_record(record_data)
        retrieved_record = test_db.get_record_by_id(added_record.id)

        assert retrieved_record is not None
        assert retrieved_record.id == added_record.id
        assert retrieved_record.room == '1.01'

    def test_get_last_record(self, test_db):
        """Тест получения последней записи"""
        # Добавляем несколько записей
        test_db.add_record({
            'message_id': 1004,
            'date': datetime.now(),
            'quantity': 10,
            'capacity': 27
        })

        test_db.add_record({
            'message_id': 1005,
            'date': datetime.now(),
            'quantity': -2,
            'capacity': 27,
            'room': '2.01'
        })

        last_record = test_db.get_last_record()
        assert last_record is not None
        assert last_record.message_id == 1005

    def test_get_records_by_room(self, test_db):
        """Тест получения записей по комнате"""
        # Добавляем записи для разных комнат
        test_db.add_record({
            'message_id': 1006,
            'date': datetime.now(),
            'quantity': -1,
            'capacity': 27,
            'room': '1.01'
        })

        test_db.add_record({
            'message_id': 1007,
            'date': datetime.now(),
            'quantity': -1,
            'capacity': 27,
            'room': '2.01'
        })

        test_db.add_record({
            'message_id': 1008,
            'date': datetime.now(),
            'quantity': -1,
            'capacity': 27,
            'room': '1.01'
        })

        records = test_db.get_records_by_room('1.01')
        assert len(records) == 2
        assert all(record.room == '1.01' for record in records)

    def test_get_balance(self, test_db):
        """Тест расчета баланса"""
        # Приход 27л
        test_db.add_record({
            'message_id': 1009,
            'date': datetime.now(),
            'quantity': 10,
            'capacity': 27
        })

        # Приход 12л
        test_db.add_record({
            'message_id': 1010,
            'date': datetime.now(),
            'quantity': 5,
            'capacity': 12
        })

        # Расход 27л
        test_db.add_record({
            'message_id': 1011,
            'date': datetime.now(),
            'quantity': -3,
            'capacity': 27,
            'room': '1.01'
        })

        # Расход 12л
        test_db.add_record({
            'message_id': 1012,
            'date': datetime.now(),
            'quantity': -2,
            'capacity': 12,
            'room': '2.01'
        })

        balance_27, balance_12 = test_db.get_balance()
        assert balance_27 == 7  # 10 - 3
        assert balance_12 == 3  # 5 - 2

    def test_record_to_dict(self, test_db):
        """Тест конвертации записи в словарь"""
        record_data = {
            'message_id': 1013,
            'date': datetime.now(),
            'quantity': -1,
            'capacity': 27,
            'room': '3.01',
            'amount': 1000,
            'receiver': 'Иван',
            'sender_user_id': 12345,
            'sender_name': 'Test User'
        }

        record = test_db.add_record(record_data)
        record_dict = test_db.record_to_dict(record)

        assert isinstance(record_dict, dict)
        assert record_dict['quantity'] == -1
        assert record_dict['room'] == '3.01'
        assert record_dict['amount'] == 1000
        assert record_dict['receiver'] == 'Иван'

    def test_clear_all_records(self, test_db):
        """Тест очистки всех записей"""
        # Добавляем записи
        test_db.add_record({
            'message_id': 1014,
            'date': datetime.now(),
            'quantity': 5,
            'capacity': 27
        })

        # Проверяем что записи есть
        assert test_db.get_last_record() is not None

        # Очищаем
        test_db.clear_all_records()

        # Проверяем что записей нет
        assert test_db.get_last_record() is None

    def test_get_record_by_message_id(self, test_db):
        """Тест получения записи по message_id"""
        record_data = {
            'message_id': 1015,
            'date': datetime.now(),
            'quantity': 8,
            'capacity': 27
        }

        added_record = test_db.add_record(record_data)
        retrieved_record = test_db.get_record_by_message_id(1015)

        assert retrieved_record is not None
        assert retrieved_record.id == added_record.id
        assert retrieved_record.message_id == 1015


class TestDatabaseEdgeCases:
    """Тесты граничных случаев для Database"""

    def test_empty_database(self, test_db):
        """Тест работы с пустой БД"""
        assert test_db.get_last_record() is None
        assert test_db.get_record_by_id(999) is None
        assert test_db.get_record_by_message_id(999) is None

        balance_27, balance_12 = test_db.get_balance()
        assert balance_27 == 0
        assert balance_12 == 0

        records = test_db.get_records_by_room('1.01')
        assert records == []

    def test_record_to_dict_none(self, test_db):
        """Тест конвертации None в record_to_dict"""
        result = test_db.record_to_dict(None)
        assert result is None

    def test_balance_only_arrivals(self, test_db):
        """Тест баланса только с приходом"""
        test_db.add_record({'message_id': 1016, 'date': datetime.now(), 'quantity': 15, 'capacity': 27})
        test_db.add_record({'message_id': 1017, 'date': datetime.now(), 'quantity': 8, 'capacity': 12})

        balance_27, balance_12 = test_db.get_balance()
        assert balance_27 == 15
        assert balance_12 == 8

    def test_balance_only_consumption(self, test_db):
        """Тест баланса только с расходом"""
        test_db.add_record({'message_id': 1018, 'date': datetime.now(), 'quantity': -5, 'capacity': 27})
        test_db.add_record({'message_id': 1019, 'date': datetime.now(), 'quantity': -3, 'capacity': 12})

        balance_27, balance_12 = test_db.get_balance()
        assert balance_27 == -5
        assert balance_12 == -3