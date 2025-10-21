import sys
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, GasRecord

sys.path.append(os.path.dirname(__file__))

try:
    from config import DATABASE_URL
except ImportError:
    from src.config import DATABASE_URL


class Database:
    def __init__(self, db_url=None):
        # Если запущены тесты - используем тестовую БД
        if 'pytest' in sys.modules:
            db_url = 'sqlite:///test_gas.db'
            print(f"🧪 Test mode: using {db_url}")
        elif db_url is None:
            db_url = DATABASE_URL

        self.db_url = db_url
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def add_record(self, record_data):
        """Добавляет новую запись в БД"""
        session = self.get_session()
        try:
            # Проверяем, существует ли уже запись с таким message_id
            existing = session.query(GasRecord).filter_by(
                message_id=record_data['message_id']
            ).first()
            if existing:
                return existing

            record = GasRecord(**record_data)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def record_to_dict(self, record):
        """Конвертирует объект GasRecord в словарь"""
        if record is None:
            return None

        return {
            'id': record.id,
            'message_id': record.message_id,
            'date': record.date,
            'quantity': record.quantity,
            'capacity': record.capacity,
            'room': record.room,
            'amount': record.amount,
            'receiver': record.receiver,
            'comments': record.comments,
            'linked_record_id': record.linked_record_id,
            'sender_user_id': record.sender_user_id,
            'sender_name': record.sender_name,
            'payment_date': record.payment_date
        }

    def get_record_by_id(self, record_id):
        """Получает запись по ID"""
        session = self.get_session()
        try:
            return session.query(GasRecord).filter_by(id=record_id).first()
        finally:
            session.close()

    def get_last_record(self):
        """Получает последнюю запись"""
        session = self.get_session()
        try:
            return session.query(GasRecord).order_by(GasRecord.id.desc()).first()
        finally:
            session.close()

    def get_record_by_message_id(self, message_id):
        """Получает запись по message_id"""
        session = self.get_session()
        try:
            return session.query(GasRecord).filter_by(message_id=message_id).first()
        finally:
            session.close()

    def get_records_by_room(self, room, limit=10):
        """Получает записи по комнате"""
        session = self.get_session()
        try:
            return session.query(GasRecord).filter(
                GasRecord.room == room
            ).order_by(GasRecord.id.desc()).limit(limit).all()
        finally:
            session.close()

    def get_balance(self):
        """Вычисляет текущий баланс баллонов"""
        session = self.get_session()
        try:
            records = session.query(GasRecord).all()
            balance_27 = 0
            balance_12 = 0

            for record in records:
                if record.quantity:
                    if record.capacity == 27:
                        balance_27 += record.quantity
                    elif record.capacity == 12:
                        balance_12 += record.quantity

            return balance_27, balance_12
        finally:
            session.close()

    def clear_all_records(self):
        """Удаляет все записи (только для тестов!)"""
        if 'test' not in self.db_url:
            raise RuntimeError(
                "🚨 DANGER: Попытка очистить production БД! "
                "Метод clear_all_records() можно использовать только с тестовой БД."
            )

        session = self.get_session()
        try:
            session.query(GasRecord).delete()
            session.commit()
        finally:
            session.close()

    def drop_all_tables(self):
        """Удаляет все таблицы (только для тестов!)"""
        if 'test' not in self.db_url:
            raise RuntimeError(
                "🚨 DANGER: Попытка удалить production БД! "
                "Метод drop_all_tables() можно использовать только с тестовой БД."
            )

        Base.metadata.drop_all(self.engine)