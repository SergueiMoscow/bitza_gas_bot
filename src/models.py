from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class GasRecord(Base):
    __tablename__ = 'gas_records'

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, unique=True, nullable=False)
    date = Column(DateTime, default=datetime.now)
    quantity = Column(Integer)
    capacity = Column(Integer, default=27)
    room = Column(String(20))
    amount = Column(Float)
    receiver = Column(String(100))
    comments = Column(Text)
    linked_record_id = Column(Integer, ForeignKey('gas_records.id'))

    # Новые поля для пользователя
    sender_user_id = Column(Integer)
    sender_name = Column(String(200))

    linked_record = relationship('GasRecord', remote_side=[id], backref='linked_records')