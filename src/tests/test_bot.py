import pytest


class TestGasBotMessages:
    """Тесты обработки сообщений ботом"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message_text,expected_quantity,expected_room,expected_amount", [
        # Приход баллонов
        ("+5", 5, None, None),
        ("+10 27", 10, None, None),
        ("+3 12", 3, None, None),

        # Расход
        ("-1 2.01", -1, "2.01", None),
        ("-2 3.5", -2, "3.05", None),
        ("-1 дом", -1, "дом", None),

        # Расход с оплатой
        ("-1 2.01 1000 Иван", -1, "2.01", 1000),
        ("-2 3.5 1500 Мария", -2, "3.05", 1500),

        # Оплата
        ("1000 2.01 Мария", None, "2.01", 1000),
        ("1500 3.5", None, "3.05", 1500),
    ])
    async def test_process_gas_message_basic(
            self, gas_bot, mock_update, mock_context,
            message_text, expected_quantity, expected_room, expected_amount
    ):
        """Тест базовой обработки газовых сообщений"""
        mock_update.message.text = message_text

        # Обрабатываем сообщение
        await gas_bot.process_gas_message(
            mock_update,
            mock_context,
            message_text,
            mock_update.message.from_user
        )

        # Проверяем, что запись создана
        last_record = gas_bot.db.get_last_record()
        assert last_record is not None
        assert last_record.quantity == expected_quantity
        assert last_record.room == expected_room
        assert last_record.amount == expected_amount

        # Проверяем, что отправлено подтверждение или уведомление
        assert mock_update.message.reply_text.called or mock_context.bot.send_message.called

    @pytest.mark.asyncio
    async def test_prepayment_then_gas_consumption(self, gas_bot, mock_update, mock_context):
        """Тест: предоплата, затем взятие газа"""
        user = mock_update.message.from_user

        # Шаг 1: Предоплата
        mock_update.message.text = "1000 2.01 Иван"
        mock_update.message.message_id = 2001
        await gas_bot.process_gas_message(mock_update, mock_context, "1000 2.01 Иван", user)

        prepayment = gas_bot.db.get_last_record()
        assert prepayment.amount == 1000
        assert prepayment.room == "2.01"
        assert prepayment.quantity is None
        assert prepayment.payment_date is not None
        prepayment_id = prepayment.id

        # Шаг 2: Взятие газа
        mock_update.message.text = "-1 2.01"
        mock_update.message.message_id = 2002
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 2.01", user)

        # Проверяем, что предоплата обновлена
        prepayment_updated = gas_bot.db.get_record_by_id(prepayment_id)
        assert prepayment_updated.quantity == -1
        assert prepayment_updated.amount == 1000
        assert prepayment_updated.receiver == "Иван"

    @pytest.mark.asyncio
    async def test_gas_consumption_then_payment(self, gas_bot, mock_update, mock_context):
        """Тест: взятие газа, затем оплата"""
        user = mock_update.message.from_user

        # Шаг 1: Взятие газа без оплаты
        mock_update.message.text = "-1 3.05"
        mock_update.message.message_id = 3001
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 3.05", user)

        gas_record = gas_bot.db.get_last_record()
        assert gas_record.quantity == -1
        assert gas_record.room == "3.05"
        assert gas_record.amount is None
        assert gas_record.payment_date is None
        gas_record_id = gas_record.id

        # Шаг 2: Оплата
        mock_update.message.text = "1000 3.05 Мария"
        mock_update.message.message_id = 3002
        await gas_bot.process_gas_message(mock_update, mock_context, "1000 3.05 Мария", user)

        # Проверяем, что к газовой записи добавлена оплата
        gas_record_updated = gas_bot.db.get_record_by_id(gas_record_id)
        assert gas_record_updated.amount == 1000
        assert gas_record_updated.receiver == "Мария"
        assert gas_record_updated.payment_date is not None

    @pytest.mark.asyncio
    async def test_gas_consumption_with_immediate_payment(self, gas_bot, mock_update, mock_context):
        """Тест: взятие газа сразу с оплатой"""
        user = mock_update.message.from_user

        mock_update.message.text = "-1 4.10 1200 Анна"
        mock_update.message.message_id = 4001
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 4.10 1200 Анна", user)

        record = gas_bot.db.get_last_record()
        assert record.quantity == -1
        assert record.room == "4.10"
        assert record.amount == 1200
        assert record.receiver == "Анна"
        assert record.payment_date is not None

    @pytest.mark.asyncio
    async def test_balance_calculation(self, gas_bot, mock_update, mock_context):
        """Тест расчета баланса"""
        user = mock_update.message.from_user

        # Добавляем приход
        mock_update.message.text = "+10 27"
        mock_update.message.message_id = 5001
        await gas_bot.process_gas_message(mock_update, mock_context, "+10 27", user)

        # Добавляем расход
        mock_update.message.text = "-3 1.01"
        mock_update.message.message_id = 5002
        await gas_bot.process_gas_message(mock_update, mock_context, "-3 1.01", user)

        # Проверяем баланс
        balance_27, balance_12 = gas_bot.db.get_balance()
        assert balance_27 == 7  # 10 - 3
        assert balance_12 == 0

    @pytest.mark.asyncio
    async def test_balance_with_different_capacities(self, gas_bot, mock_update, mock_context):
        """Тест расчета баланса с разными емкостями"""
        user = mock_update.message.from_user

        # Приход 27л
        mock_update.message.text = "+5 27"
        mock_update.message.message_id = 5101
        await gas_bot.process_gas_message(mock_update, mock_context, "+5 27", user)

        # Приход 12л
        mock_update.message.text = "+3 12"
        mock_update.message.message_id = 5102
        await gas_bot.process_gas_message(mock_update, mock_context, "+3 12", user)

        # Расход 27л
        mock_update.message.text = "-1 27 1.01"
        mock_update.message.message_id = 5103
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 27 1.01", user)

        balance_27, balance_12 = gas_bot.db.get_balance()
        assert balance_27 == 4  # 5 - 1
        assert balance_12 == 3

    @pytest.mark.asyncio
    async def test_duplicate_message_handling(self, gas_bot, mock_update, mock_context):
        """Тест обработки дубликатов сообщений"""
        user = mock_update.message.from_user

        # Отправляем сообщение дважды с одинаковым message_id
        mock_update.message.text = "+5"
        mock_update.message.message_id = 6001

        await gas_bot.process_gas_message(mock_update, mock_context, "+5", user)
        await gas_bot.process_gas_message(mock_update, mock_context, "+5", user)

        # Должна быть только одна запись
        session = gas_bot.db.get_session()
        from src.models import GasRecord
        count = session.query(GasRecord).filter_by(message_id=6001).count()
        session.close()

        assert count == 1

    @pytest.mark.asyncio
    async def test_unauthorized_user(self, gas_bot, mock_update, mock_context):
        """Тест доступа неавторизованного пользователя"""
        # Меняем ID на неразрешенного пользователя
        mock_update.message.from_user.id = 99999
        mock_update.message.text = "+5"

        await gas_bot.handle_gas_message(mock_update, mock_context)

        # Проверяем, что отправлено сообщение об отказе
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "нет доступа" in call_args.lower()

    @pytest.mark.asyncio
    async def test_invalid_message_format(self, gas_bot, mock_update, mock_context):
        """Тест невалидного формата сообщения"""
        mock_update.message.text = "какой-то текст без данных"

        await gas_bot.handle_gas_message(mock_update, mock_context)

        # Проверяем, что отправлено сообщение об ошибке
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "неверный формат" in call_args.lower()

    @pytest.mark.asyncio
    async def test_room_history_request(self, gas_bot, mock_update, mock_context, sample_gas_records):
        """Тест запроса истории по комнате"""
        mock_update.message.text = "2.01"

        await gas_bot.handle_gas_message(mock_update, mock_context)

        # Проверяем, что отправлена история
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "история" in call_args.lower() or "2.01" in call_args

    @pytest.mark.asyncio
    async def test_auto_fill_receiver(self, gas_bot, mock_update, mock_context):
        """Тест автоматического заполнения получателя при оплате"""
        user = mock_update.message.from_user
        user.first_name = "Петр"

        # Оплата без указания получателя
        mock_update.message.text = "1000 5.01"
        mock_update.message.message_id = 7001
        await gas_bot.process_gas_message(mock_update, mock_context, "1000 5.01", user)

        record = gas_bot.db.get_last_record()
        assert record.receiver == "Петр"  # Должен автоматически подставиться

    @pytest.mark.asyncio
    async def test_multiple_operations_same_room(self, gas_bot, mock_update, mock_context):
        """Тест множественных операций с одной комнатой"""
        user = mock_update.message.from_user

        # 1. Предоплата
        mock_update.message.text = "1000 5.05 Сергей"
        mock_update.message.message_id = 8001
        await gas_bot.process_gas_message(mock_update, mock_context, "1000 5.05 Сергей", user)

        # 2. Взятие газа (должно связаться с предоплатой)
        mock_update.message.text = "-1 5.05"
        mock_update.message.message_id = 8002
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 5.05", user)

        # 3. Еще одно взятие газа (без оплаты)
        mock_update.message.text = "-1 5.05"
        mock_update.message.message_id = 8003
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 5.05", user)

        # 4. Оплата за второе взятие
        mock_update.message.text = "1000 5.05 Сергей"
        mock_update.message.message_id = 8004
        await gas_bot.process_gas_message(mock_update, mock_context, "1000 5.05 Сергей", user)

        # Проверяем записи по комнате
        records = gas_bot.db.get_records_by_room('5.05')
        assert len(records) >= 2

    @pytest.mark.asyncio
    async def test_prepayment_without_gas_consumption(self, gas_bot, mock_update, mock_context):
        """Тест предоплаты без последующего взятия газа (висящая предоплата)"""
        user = mock_update.message.from_user

        mock_update.message.text = "1500 6.01 Ольга"
        mock_update.message.message_id = 9001
        await gas_bot.process_gas_message(mock_update, mock_context, "1500 6.01 Ольга", user)

        record = gas_bot.db.get_last_record()
        assert record.amount == 1500
        assert record.room == "6.01"
        assert record.quantity is None  # Нет расхода
        assert record.payment_date is not None  # Есть дата оплаты
        assert record.linked_record_id is None  # Не связана

    @pytest.mark.asyncio
    async def test_gas_without_payment(self, gas_bot, mock_update, mock_context):
        """Тест взятия газа без оплаты (долг)"""
        user = mock_update.message.from_user

        mock_update.message.text = "-1 7.01"
        mock_update.message.message_id = 10001
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 7.01", user)

        record = gas_bot.db.get_last_record()
        assert record.quantity == -1
        assert record.room == "7.01"
        assert record.amount is None  # Нет оплаты
        assert record.payment_date is None  # Нет даты оплаты

    @pytest.mark.asyncio
    async def test_format_record_display(self, gas_bot):
        """Тест форматирования записи для отображения"""
        from src.models import GasRecord
        from datetime import datetime

        # Создаем тестовую запись
        record = GasRecord(
            message_id=11001,
            date=datetime.now(),
            quantity=-1,
            capacity=27,
            room='1.05',
            amount=1000,
            receiver='Тест',
            payment_date=datetime.now(),
            comments='композитный',
            sender_user_id=12345,
            sender_name='Admin'
        )

        formatted = gas_bot.format_record(record)

        assert '-1' in formatted
        assert '27' in formatted or '27л' in formatted
        assert '1.05' in formatted or '1.5' in formatted
        assert '1000' in formatted
        assert 'Тест' in formatted
        assert 'композитный' in formatted

    @pytest.mark.asyncio
    async def test_notification_sent_to_other_users(self, gas_bot, mock_update, mock_context):
        """Тест рассылки уведомлений другим пользователям"""
        user = mock_update.message.from_user

        mock_update.message.text = "+5"
        mock_update.message.message_id = 12001

        await gas_bot.process_gas_message(mock_update, mock_context, "+5", user)

        # Проверяем что метод send_message был вызван для уведомления других пользователей
        # (в реальности будет вызван для всех кроме отправителя)
        assert mock_context.bot.send_message.called or mock_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_room_with_dom(self, gas_bot, mock_update, mock_context):
        """Тест работы с комнатой 'дом'"""
        user = mock_update.message.from_user

        mock_update.message.text = "-1 дом 1000 Администратор"
        mock_update.message.message_id = 13001
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 дом 1000 Администратор", user)

        record = gas_bot.db.get_last_record()
        assert record.quantity == -1
        assert record.room == "дом"
        assert record.amount == 1000
        assert record.receiver == "Администратор"

    @pytest.mark.asyncio
    async def test_arrival_without_room(self, gas_bot, mock_update, mock_context):
        """Тест прихода баллонов (без комнаты)"""
        user = mock_update.message.from_user

        mock_update.message.text = "+8 27"
        mock_update.message.message_id = 14001
        await gas_bot.process_gas_message(mock_update, mock_context, "+8 27", user)

        record = gas_bot.db.get_last_record()
        assert record.quantity == 8
        assert record.capacity == 27
        assert record.room is None

    @pytest.mark.asyncio
    async def test_normalized_room_numbers(self, gas_bot, mock_update, mock_context):
        """Тест нормализации номеров комнат при обработке"""
        user = mock_update.message.from_user

        # Отправляем с форматом 1.5 (должно стать 1.05)
        mock_update.message.text = "-1 1.5"
        mock_update.message.message_id = 15001
        await gas_bot.process_gas_message(mock_update, mock_context, "-1 1.5", user)

        record = gas_bot.db.get_last_record()
        assert record.room == "1.05"  # Нормализовано

    @pytest.mark.asyncio
    async def test_sender_info_saved(self, gas_bot, mock_update, mock_context):
        """Тест сохранения информации об отправителе"""
        user = mock_update.message.from_user
        user.id = 12345
        user.first_name = "Иван"
        user.last_name = "Петров"

        mock_update.message.text = "+5"
        mock_update.message.message_id = 16001
        await gas_bot.process_gas_message(mock_update, mock_context, "+5", user)

        record = gas_bot.db.get_last_record()
        assert record.sender_user_id == 12345
        assert "Иван" in record.sender_name
        assert "Петров" in record.sender_name


class TestGasBotCommands:
    """Тесты команд бота"""

    @pytest.mark.asyncio
    async def test_balance_command(self, gas_bot, mock_update, mock_context):
        """Тест команды /balance"""
        # Добавляем немного баллонов
        user = mock_update.message.from_user
        mock_update.message.text = "+5 27"
        mock_update.message.message_id = 17001
        await gas_bot.process_gas_message(mock_update, mock_context, "+5 27", user)

        # Вызываем команду balance
        await gas_bot.balance_command(mock_update, mock_context)

        # Проверяем что ответ был отправлен
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "остаток" in call_args.lower() or "баллон" in call_args.lower()

    @pytest.mark.asyncio
    async def test_last_command(self, gas_bot, mock_update, mock_context, sample_gas_records):
        """Тест команды /last"""
        await gas_bot.last_command(mock_update, mock_context)

        # Проверяем что ответ был отправлен
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "движени" in call_args.lower() or "баллон" in call_args.lower()

    @pytest.mark.asyncio
    async def test_my_id_command_authorized(self, gas_bot, mock_update, mock_context):
        """Тест команды /my_id для авторизованного пользователя"""
        mock_update.message.from_user.id = 12345  # Авторизованный ID

        await gas_bot.my_id_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "12345" in call_args

    @pytest.mark.asyncio
    async def test_my_id_command_unauthorized(self, gas_bot, mock_update, mock_context):
        """Тест команды /my_id для неавторизованного пользователя"""
        mock_update.message.from_user.id = 99999  # Неавторизованный ID

        await gas_bot.my_id_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "99999" in call_args
        assert "нет в списке" in call_args.lower()


class TestGasBotValidation:
    """Тесты валидации сообщений"""

    def test_valid_gas_message_with_quantity(self, gas_bot):
        """Тест валидации сообщения с количеством"""
        assert gas_bot.is_valid_gas_message("+5") is True
        assert gas_bot.is_valid_gas_message("-1 2.01") is True

    def test_valid_gas_message_with_amount(self, gas_bot):
        """Тест валидации сообщения с суммой"""
        assert gas_bot.is_valid_gas_message("1000 2.01 Иван") is True
        assert gas_bot.is_valid_gas_message("2.01 1000") is True

    def test_invalid_gas_message(self, gas_bot):
        """Тест валидации невалидного сообщения"""
        assert gas_bot.is_valid_gas_message("просто текст") is False
        assert gas_bot.is_valid_gas_message("комментарий") is False
        assert gas_bot.is_valid_gas_message("50") is False  # Не подходит под критерии

    def test_valid_room_number_message(self, gas_bot):
        """Тест, что номер комнаты сам по себе не валидное газовое сообщение"""
        # Номер комнаты должен показывать историю, а не считаться газовым сообщением
        assert gas_bot.is_valid_gas_message("2.01") is False
        assert gas_bot.is_valid_gas_message("дом") is False