import sys
import os

sys.path.append(os.path.dirname(__file__))

from flask import Flask, render_template, request, jsonify
from database import Database
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

from models import GasRecord

try:
    from config import WEB_APP_DOMAIN
except ImportError:
    from src.config import WEB_APP_DOMAIN

app = Flask(__name__, template_folder='web_templates')
db = Database()


@app.route('/')
def index():
    """Главная страница для проверки домена (публичная)"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Gas Bot Web App</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Gas Bot Web App</h1>
            <p>Сервис для учета газовых баллонов</p>
            <p>Домен: {WEB_APP_DOMAIN}</p>
            <p>Для доступа к функциям используйте Telegram бота</p>
            <hr>
            <p><small>{WEB_APP_DOMAIN}</small></p>
        </div>
    </body>
    </html>
    """


@app.route('/web_last')
def web_last():
    """Web App для последних движений"""
    user_id = request.args.get('user_id')

    # Простая проверка (можно усилить)
    if not user_id:
        return "Доступ запрещен", 403

    session = db.get_session()
    try:
        records = session.query(GasRecord).order_by(GasRecord.id.desc()).limit(20).all()
        records_data = []
        for record in records:
            records_data.append({
                'quantity': record.quantity,
                'capacity': record.capacity,
                'room': record.room,
                'amount': record.amount,
                'receiver': record.receiver,
                'comments': record.comments,
                'date': record.date
            })

        return render_template('last_movements.html',
                               records=records_data,
                               current_time=datetime.now().strftime('%d.%m.%Y %H:%M'))
    finally:
        session.close()


@app.route('/web_debts')
def web_debts():
    """Web App для долгов и предоплат"""
    user_id = request.args.get('user_id')

    if not user_id:
        return "Доступ запрещен", 403

    session = db.get_session()
    try:
        # Неоплаченные баллоны (расход без оплаты)
        unpaid_balloons = session.query(GasRecord).filter(
            GasRecord.quantity < 0,
            GasRecord.amount.is_(None)  # Используем is_ вместо == None
        ).order_by(GasRecord.date.desc()).all()

        # Предоплаты (оплата без взятия баллона)
        prepayments = session.query(GasRecord).filter(
            GasRecord.amount.is_not(None),  # Используем is_not вместо != None
            GasRecord.quantity.is_(None)
        ).order_by(GasRecord.date.desc()).all()

        return render_template('debts.html',
                               unpaid_balloons=unpaid_balloons,
                               prepayments=prepayments,
                               current_time=datetime.now().strftime('%d.%m.%Y %H:%M'))
    finally:
        session.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)