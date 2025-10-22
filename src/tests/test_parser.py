import pytest
from datetime import datetime
from unittest.mock import MagicMock
from src.parser import MessageParser
from src.models import GasRecord


class TestMessageParserNormalization:
    """Тесты нормализации номеров комнат"""

    def test_normalize_room_number_dom(self):
        """Тест нормализации комнаты 'дом'"""
        assert MessageParser.normalize_room_number('дом') == 'дом'
        assert MessageParser.normalize_room_number('ДОМ') == 'дом'

    def test_normalize_room_number_single_digit(self):
        """Тест нормализации комнат с одной цифрой после точки"""
        assert MessageParser.normalize_room_number('1.5') == '1.05'
        assert MessageParser.normalize_room_number('2.1') == '2.01'
        assert MessageParser.normalize_room_number('3.9') == '3.09'

    def test_normalize_room_number_double_digit(self):
        """Тест нормализации комнат с двумя цифрами после точки"""
        assert MessageParser.normalize_room_number('1.05') == '1.05'
        assert MessageParser.normalize_room_number('2.15') == '2.15'
        assert MessageParser.normalize_room_number('3.10') == '3.10'

    def test_normalize_room_number_invalid(self):
        """Тест нормализации невалидных номеров комнат"""
        assert MessageParser.normalize_room_number('просто текст') == 'просто текст'
        assert MessageParser.normalize_room_number('123') == '123'
        assert MessageParser.normalize_room_number('') == ''


class TestMessageParserBasic:
    """Тесты базового парсинга сообщений"""

    def test_parse_empty_message(self):
        """Тест парсинга пустого сообщения"""
        result = MessageParser.parse_message('')
        expected = {
            'quantity': None,
            'capacity': 27,
            'room': None,
            'amount': None,
            'receiver': None,
        }
        assert result['quantity'] is None
        assert result['capacity'] == 27
        assert result['room'] is None
        assert result['amount'] is None
        assert result['receiver'] is None

    def test_parse_arrival_only(self):
        """Тест парсинга прихода баллонов"""
        result = MessageParser.parse_message('+5')
        assert result['quantity'] == 5
        assert result['capacity'] == 27
        assert result['room'] is None
        assert result['amount'] is None

    def test_parse_arrival_with_capacity(self):
        """Тест парсинга прихода с указанием емкости"""
        result = MessageParser.parse_message('+3 12')
        assert result['quantity'] == 3
        assert result['capacity'] == 12
        assert result['room'] is None

    def test_parse_consumption(self):
        """Тест парсинга расхода"""
        result = MessageParser.parse_message('-1 2.01')
        assert result['quantity'] == -1
        assert result['room'] == '2.01'

    def test_parse_consumption_with_dom(self):
        """Тест парсинга расхода для 'дом'"""
        result = MessageParser.parse_message('-1 дом')
        assert result['quantity'] == -1
        assert result['room'] == 'дом'

    def test_parse_consumption_with_payment(self):
        """Тест парсинга расхода с оплатой"""
        result = MessageParser.parse_message('-1 2.01 1000 Иван')
        assert result['quantity'] == -1
        assert result['room'] == '2.01'
        assert result['amount'] == 1000
        assert result['receiver'] == 'Иван'

    def test_parse_payment_only(self):
        """Тест парсинга только оплаты"""
        result = MessageParser.parse_message('1000 2.01 Мария')
        assert result['quantity'] is None
        assert result['room'] == '2.01'
        assert result['amount'] == 1000
        assert result['receiver'] == 'Мария'

    def test_parse_payment_alternative_format(self):
        """Тест парсинга оплаты в альтернативном формате"""
        result = MessageParser.parse_message('2.01 1000')
        assert result['room'] == '2.01'
        assert result['amount'] == 1000


class TestMessageParserEdgeCases:
    """Тесты граничных случаев парсера"""

    def test_parse_large_quantity_not_recognized(self):
        """Тест что большие количества не распознаются как quantity"""
        result = MessageParser.parse_message('+15')
        assert result['quantity'] is None  # +15 вне диапазона -10 до +10

        result = MessageParser.parse_message('-20')
        assert result['quantity'] is None

    def test_parse_small_amount_not_recognized(self):
        """Тест что маленькие суммы не распознаются как amount"""
        result = MessageParser.parse_message('50')
        assert result['amount'] is None  # 50 меньше 100

        result = MessageParser.parse_message('99')
        assert result['amount'] is None

    def test_parse_comments(self):
        """Тест парсинга комментариев"""
        result = MessageParser.parse_message('-1 2.01 1000 Иван композитный новый')
        assert result['quantity'] == -1
        assert result['room'] == '2.01'
        assert result['amount'] == 1000
        assert result['receiver'] == 'Иван'
        assert result['comments'] == 'композитный новый'

    def test_parse_multiple_names(self):
        """Тест парсинга когда есть несколько имен"""
        result = MessageParser.parse_message('1000 2.01 Иван Петр')
        assert result['receiver'] == 'Иван'  # первое имя - получатель
        assert result['comments'] == 'Петр'  # второе имя - комментарий

    def test_parse_lowercase_name_in_comments(self):
        """Тест что имена в нижнем регистре идут в комментарии"""
        result = MessageParser.parse_message('1000 2.01 иван')
        assert result['receiver'] is None  # имя в нижнем регистре не распознается
        assert result['comments'] == 'иван'

    def test_parse_complex_message(self):
        """Тест парсинга сложного сообщения"""
        result = MessageParser.parse_message('-2 3.05 1500 Сергей композитный баллон')
        assert result['quantity'] == -2
        assert result['room'] == '3.05'
        assert result['amount'] == 1500
        assert result['receiver'] == 'Сергей'
        assert result['comments'] == 'композитный баллон'


class TestMessageParserRoomNormalizationInContext:
    """Тесты нормализации комнат в контексте парсинга"""

    def test_room_normalization_during_parsing(self):
        """Тест что номера комнат нормализуются при парсинге"""
        result = MessageParser.parse_message('-1 1.5')
        assert result['room'] == '1.05'

        result = MessageParser.parse_message('1000 2.1')
        assert result['room'] == '2.01'

    def test_room_normalization_preserves_double_digit(self):
        """Тест что двузначные номера комнат не меняются"""
        result = MessageParser.parse_message('-1 1.15')
        assert result['room'] == '1.15'

        result = MessageParser.parse_message('1000 2.10')
        assert result['room'] == '2.10'


class TestFindUnpaidGasRecord:
    """Тесты поиска неоплаченных записей о газе"""

    def test_find_unpaid_gas_record_exists(self):
        """Тест поиска существующей неоплаченной записи"""
        # Создаем мок сессии
        mock_session = MagicMock()

        # Создаем мок записи о неоплаченном газе
        mock_unpaid_record = GasRecord(
            id=1,
            room='2.01',
            quantity=-1,
            payment_date=None
        )

        # Настраиваем мок запроса
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = mock_unpaid_record

        result = MessageParser.find_unpaid_gas_record(mock_session, '2.01')

        assert result == mock_unpaid_record
        mock_session.query.assert_called_with(GasRecord)

    def test_find_unpaid_gas_record_not_exists(self):
        """Тест когда неоплаченной записи нет"""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = None

        result = MessageParser.find_unpaid_gas_record(mock_session, '3.05')

        assert result is None

    def test_find_unpaid_gas_record_empty_room(self):
        """Тест поиска с пустой комнатой"""
        mock_session = MagicMock()
        result = MessageParser.find_unpaid_gas_record(mock_session, '')

        assert result is None
        mock_session.query.assert_not_called()

    def test_find_unpaid_gas_record_none_room(self):
        """Тест поиска с None комнатой"""
        mock_session = MagicMock()
        result = MessageParser.find_unpaid_gas_record(mock_session, None)

        assert result is None
        mock_session.query.assert_not_called()


class TestFindPrepaymentRecord:
    """Тесты поиска предоплат"""

    def test_find_prepayment_record_exists(self):
        """Тест поиска существующей предоплаты"""
        mock_session = MagicMock()

        mock_prepayment = GasRecord(
            id=2,
            room='4.10',
            amount=1000,
            quantity=None,
            payment_date=datetime.now(),
            linked_record_id=None
        )

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = mock_prepayment

        result = MessageParser.find_prepayment_record(mock_session, '4.10')

        assert result == mock_prepayment
        mock_session.query.assert_called_with(GasRecord)

    def test_find_prepayment_record_not_exists(self):
        """Тест когда предоплаты нет"""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = None

        result = MessageParser.find_prepayment_record(mock_session, '5.05')

        assert result is None

    def test_find_prepayment_record_with_quantity(self):
        """Тест что записи с quantity не считаются предоплатой"""
        mock_session = MagicMock()

        # Запись с quantity (это не предоплата)
        mock_not_prepayment = GasRecord(
            id=4,
            room='7.01',
            amount=1000,
            quantity=-1,  # есть quantity - это не предоплата
            payment_date=datetime.now(),
            linked_record_id=None
        )

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = None

        result = MessageParser.find_prepayment_record(mock_session, '7.01')

        assert result is None

    def test_find_prepayment_record_empty_room(self):
        """Тест поиска предоплаты с пустой комнатой"""
        mock_session = MagicMock()
        result = MessageParser.find_prepayment_record(mock_session, '')

        assert result is None
        mock_session.query.assert_not_called()


class TestMessageParserIntegration:
    """Интеграционные тесты парсера"""

    @pytest.mark.parametrize("message,expected_quantity,expected_room,expected_amount,expected_receiver", [
        # Базовые случаи
        ("+5", 5, None, None, None),
        ("-1 2.01", -1, "2.01", None, None),
        ("-1 2.01 1000", -1, "2.01", 1000, None),
        ("-1 2.01 1000 Иван", -1, "2.01", 1000, "Иван"),
        ("1000 2.01", None, "2.01", 1000, None),
        ("1000 2.01 Мария", None, "2.01", 1000, "Мария"),

        # Нормализация комнат
        ("-1 1.5", -1, "1.05", None, None),
        ("1000 3.1", None, "3.01", 1000, None),

        # Комментарии
        ("-1 2.01 композитный", -1, "2.01", None, None),
        ("1000 2.01 Иван спасибо", None, "2.01", 1000, "Иван"),
    ])
    def test_parse_various_messages(self, message, expected_quantity, expected_room,
                                    expected_amount, expected_receiver):
        """Параметризованный тест различных сообщений"""
        result = MessageParser.parse_message(message)

        assert result['quantity'] == expected_quantity
        assert result['room'] == expected_room
        assert result['amount'] == expected_amount
        assert result['receiver'] == expected_receiver