import re
from typing import Dict, Any, Optional
from datetime import datetime

from src.models import GasRecord


class MessageParser:
    @staticmethod
    def normalize_room_number(room: str) -> str:
        """Нормализует номер комнаты в формат X.YY"""
        if room.lower() == 'дом':
            return 'дом'

        match = re.match(r'^(\d+)\.(\d+)$', room)
        if match:
            floor = match.group(1)
            room_num = match.group(2).zfill(2)  # Добавляем ведущий ноль если нужно
            return f"{floor}.{room_num}"
        return room

    @staticmethod
    def parse_message(text: str) -> Dict[str, Any]:
        """Парсит текст сообщения и возвращает структурированные данные"""
        result = {
            'quantity': None,
            'capacity': 27,
            'room': None,
            'amount': None,
            'receiver': None,
            'comments': []
        }

        if not text:
            return result

        # Разбиваем текст на слова
        words = text.split()

        i = 0
        while i < len(words):
            word = words[i]

            # Проверяем количество баллонов (-10 до +10)
            if re.match(r'^[+-]?\d+$', word):
                num = int(word)
                if -10 <= num <= 10 and result['quantity'] is None:
                    result['quantity'] = num
                    i += 1
                    continue

            # Проверяем емкость баллонов (12 или 27)
            if word in ['12', '27']:
                result['capacity'] = int(word)
                i += 1
                continue

            # Проверяем сумму денег (100 и выше)
            if re.match(r'^\d{3,}$', word):
                num = int(word)
                if num >= 100 and result['amount'] is None:
                    result['amount'] = num
                    i += 1
                    continue

            # Проверяем комнату (формат X.XX или X.X)
            if re.match(r'^\d+\.\d+$', word) or word.lower() == 'дом':
                normalized_room = MessageParser.normalize_room_number(word)
                result['room'] = normalized_room
                i += 1
                continue

            # Проверяем имя (начинается с заглавной буквы)
            if re.match(r'^[А-Я][а-я]*$', word):
                if result['receiver'] is None:
                    result['receiver'] = word
                    i += 1
                    continue
                else:
                    result['comments'].append(word)
                    i += 1
                    continue

            # Всё остальное - комментарии
            result['comments'].append(word)
            i += 1

        # Объединяем комментарии в строку
        result['comments'] = ' '.join(result['comments']) if result['comments'] else None

        return result

    @staticmethod
    def find_unpaid_gas_record(session, room: str) -> Optional[GasRecord]:
        """Находит запись о взятии газа без оплаты для данной комнаты"""
        if not room:
            return None

        # Ищем записи где:
        # - та же комната
        # - был взят газ (quantity < 0)
        # - нет даты оплаты (payment_date is None)
        unpaid_record = session.query(GasRecord).filter(
            GasRecord.room == room,
            GasRecord.quantity < 0,
            GasRecord.payment_date.is_(None)
        ).order_by(GasRecord.date.desc()).first()

        return unpaid_record

    @staticmethod
    def find_prepayment_record(session, room: str) -> Optional[GasRecord]:
        """Находит предоплату для данной комнаты"""
        if not room:
            return None

        # Ищем записи где:
        # - та же комната
        # - была оплата (amount > 0)
        # - есть дата оплаты (payment_date is not None)
        # - нет количества (quantity is None) - это была только оплата
        # - запись еще не связана (linked_record_id is None)
        prepayment = session.query(GasRecord).filter(
            GasRecord.room == room,
            GasRecord.amount > 0,
            GasRecord.payment_date.isnot(None),
            GasRecord.quantity.is_(None),
        ).order_by(GasRecord.payment_date.desc()).first()

        return prepayment