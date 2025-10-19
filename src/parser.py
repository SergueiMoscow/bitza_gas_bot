import re
from typing import Dict, Any

from src.models import GasRecord


class MessageParser:
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
                # Если получатель еще не указан, устанавливаем его
                if result['receiver'] is None:
                    result['receiver'] = word
                    i += 1
                    continue
                # Иначе добавляем в комментарии (могут быть несколько имен)
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
    def parse_message(text: str) -> Dict[str, Any]:
        """Парсит текст сообщения и возвращает структурированные данные"""
        result = {
            'quantity': None,
            'capacity': 27,  # значение по умолчанию
            'room': None,
            'amount': None,
            'receiver': None,
            'comments': []
        }

        if not text:
            return result

        # Разбиваем текст на слова
        words = text.split()

        for word in words:
            # Проверяем количество баллонов (-10 до +10)
            if re.match(r'^[+-]?\d+$', word):
                num = int(word)
                if -10 <= num <= 10 and result['quantity'] is None:
                    result['quantity'] = num
                    continue

            # Проверяем емкость баллонов (12 или 27)
            if word in ['12', '27']:
                result['capacity'] = int(word)
                continue

            # Проверяем сумму денег (100 и выше)
            if re.match(r'^\d{3,}$', word):
                num = int(word)
                if num >= 100 and result['amount'] is None:
                    result['amount'] = num
                    continue

            # Проверяем комнату (формат X.XX или X.X)
            if re.match(r'^\d+\.\d+$', word) or word.lower() == 'дом':
                result['room'] = word
                continue

            # Проверяем имя (начинается с заглавной буквы)
            if re.match(r'^[А-Я][а-я]*$', word) and result['receiver'] is None:
                result['receiver'] = word
                continue

            # Всё остальное - комментарии
            result['comments'].append(word)

        # Объединяем комментарии в строку
        result['comments'] = ' '.join(result['comments']) if result['comments'] else None

        return result

    @staticmethod
    def find_linked_record(session, current_record):
        """Находит связанную запись для текущей"""
        if not current_record.room:
            return None

        # Ищем записи с той же комнатой
        room_records = session.query(GasRecord).filter(
            GasRecord.room == current_record.room,
            GasRecord.id != current_record.id
        ).order_by(GasRecord.id.desc()).all()

        for record in room_records:
            # Если текущая запись - оплата, ищем взятие баллона без оплаты
            if current_record.amount and not current_record.quantity:
                if record.quantity and record.quantity < 0 and not record.amount:
                    return record

            # Если текущая запись - взятие баллона, ищем предоплату
            elif current_record.quantity and current_record.quantity < 0:
                if record.amount and not record.quantity and not record.linked_record_id:
                    return record

        return None

