from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, GasRecord
import os

from src import config


class Database:
    def __init__(self, db_url=config.DATABASE_URL):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    class Database:
        # ... остальные методы ...

        def add_record(self, record_data):
            session = self.get_session()
            try:
                # Проверяем, существует ли уже запись с таким message_id
                existing = session.query(GasRecord).filter_by(message_id=record_data['message_id']).first()
                if existing:
                    return self.record_to_dict(existing)

                record = GasRecord(**record_data)
                session.add(record)
                session.commit()
                return self.record_to_dict(record)
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        def record_to_dict(self, record):
            """Конвертирует объект GasRecord в словарь"""
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
                'sender_name': record.sender_name
            }

    def get_record_by_id(self, record_id):
        session = self.get_session()
        try:
            return session.query(GasRecord).filter_by(id=record_id).first()
        finally:
            session.close()

    def get_last_record(self):
        session = self.get_session()
        try:
            return session.query(GasRecord).order_by(GasRecord.id.desc()).first()
        finally:
            session.close()

    def get_record_by_message_id(self, message_id):
        session = self.get_session()
        try:
            return session.query(GasRecord).filter_by(message_id=message_id).first()
        finally:
            session.close()

    def get_records_by_room(self, room, limit=10):
        session = self.get_session()
        try:
            return session.query(GasRecord).filter(
                GasRecord.room == room
            ).order_by(GasRecord.id.desc()).limit(limit).all()
        finally:
            session.close()

    def get_balance(self):
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