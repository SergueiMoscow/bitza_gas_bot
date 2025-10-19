import os
import logging
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv

from database import Database
from parser import MessageParser
from models import GasRecord

# Загрузка переменных окружения
load_dotenv()

import logging

# Отключаем логи httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Или можно отключить полностью
# logging.getLogger("httpx").disabled = True
# logging.getLogger("httpcore").disabled = True

# Оставляем только важные логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class GasBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        allowed_users_str = os.getenv('ALLOWED_USER_IDS', '')
        if allowed_users_str:
            self.allowed_user_ids = [int(x.strip()) for x in allowed_users_str.split(',') if x.strip()]
        else:
            self.allowed_user_ids = []
        self.admin_user_id = int(os.getenv('ADMIN_USER_ID', 0))
        # Автоматически добавляем админа в разрешенные, если его там нет
        if self.admin_user_id and self.admin_user_id not in self.allowed_user_ids:
            self.allowed_user_ids.append(self.admin_user_id)
            print(f"DEBUG: Added admin {self.admin_user_id} to allowed users")

        print(f"DEBUG: Allowed users: {self.allowed_user_ids}")
        print(f"DEBUG: Admin ID: {self.admin_user_id}")

        self.db = Database()
        self.parser = MessageParser()

        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

        self.application = Application.builder().token(self.token).build()

        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("last", self.last_command))
        self.application.add_handler(CommandHandler("my_id", self.my_id_command))
        self.application.add_handler(CommandHandler("users", self.users_command))

        # Обработчик сообщений о газе
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_gas_message
        ))

    async def is_user_allowed(self, user_id: int) -> bool:
        """Проверяет, разрешен ли пользователь"""
        return user_id in self.allowed_user_ids

    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает ID пользователя (работает для всех, даже неавторизованных)"""
        user = update.message.from_user

        # Формируем информацию о пользователе БЕЗ Markdown разметки
        user_info = (
            f"👤 Ваши данные:\n"
            f"ID: {user.id}\n"
            f"Username: @{user.username or 'не указан'}\n"
            f"Имя: {user.first_name} {user.last_name or ''}\n\n"
        )

        if await self.is_user_allowed(user.id):
            user_info += "✅ Вы уже есть в списке разрешенных пользователей!"
        else:
            user_info += (
                "❌ Вас нет в списке разрешенных пользователей.\n"
                "Перешлите этот ID администратору для добавления."
            )

        # Отправляем БЕЗ parse_mode
        await update.message.reply_text(user_info)

        # Уведомляем администратора о запросе ID
        if not await self.is_user_allowed(user.id):
            await self.notify_admin_about_new_user(context, user, "запросил свой ID")

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список разрешенных пользователей (только для админа)"""
        user = update.message.from_user

        if user.id != self.admin_user_id:
            await update.message.reply_text("❌ Эта команда только для администратора")
            return

        users_info = []
        for user_id in self.allowed_user_ids:
            try:
                chat = await context.bot.get_chat(user_id)
                user_info = f"• {chat.first_name} {chat.last_name or ''} (@{chat.username or 'нет'}) - ID: `{user_id}`"
                users_info.append(user_info)
            except Exception:
                users_info.append(f"• Неизвестный пользователь - ID: `{user_id}`")

        message = "📋 Разрешенные пользователи:\n\n" + "\n".join(users_info)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def handle_gas_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает все сообщения о газе"""
        user = update.message.from_user
        text = update.message.text.strip()

        # Проверяем доступ
        if not await self.is_user_allowed(user.id):
            await self.notify_admin_about_new_user(context, user, text)
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту.\n"
                "Обратитесь к администратору."
            )
            return

        # Если это номер комнаты - показываем историю
        if re.match(r'^\d+\.\d+$', text) or text.lower() in ['дом', 'домой']:
            room = text.lower() if text.lower() in ['дом', 'домой'] else text
            await self.show_room_history(update, room)
            return

        # Валидация газового сообщения
        if not self.is_valid_gas_message(text):
            await update.message.reply_text(
                "❌ Неверный формат сообщения.\n\n"
                "Примеры:\n"
                "+5 27 - приход баллонов\n"
                "-1 1.01 - расход баллона\n"
                "-1 1.02 1000 Сергей - расход с оплатой\n"
                "900 2.9 Валя - оплата за предыдущий расход или предоплата\n\n"
                "Или напишите номер комнаты для просмотра истории"
            )
            return

        # Обрабатываем газовое сообщение
        await self.process_gas_message(update, context, text, user)

    async def notify_admin_about_new_user(self, context, user, action):
        """Уведомляет администратора о запросе от нового пользователя"""
        if self.admin_user_id:
            notification = (
                "🆕 Новый запрос от пользователя:\n"
                f"ID: {user.id}\n"
                f"Username: @{user.username or 'нет'}\n"
                f"Имя: {user.first_name} {user.last_name or ''}\n"
                f"Действие: {action}\n\n"
                f"Добавить в .env: ALLOWED_USER_IDS=...,{user.id}"
            )
            try:
                await context.bot.send_message(
                    chat_id=self.admin_user_id,
                    text=notification
                    # Без parse_mode для безопасности
                )
            except Exception as e:
                print(f"Не удалось уведомить администратора: {e}")

    async def process_gas_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user):
        """Обрабатывает газовое сообщение и рассылает уведомления"""
        # Парсим сообщение
        parsed_data = self.parser.parse_message(text)
        parsed_data['message_id'] = update.message.message_id
        parsed_data['date'] = update.message.date
        parsed_data['sender_user_id'] = user.id
        parsed_data['sender_name'] = f"{user.first_name} {user.last_name or ''}"

        # АВТОМАТИЧЕСКОЕ ЗАПОЛНЕНИЕ ПОЛУЧАТЕЛЯ для оплат
        # Если есть сумма денег, но нет получателя - ставим отправителя
        if parsed_data['amount'] and not parsed_data['receiver']:
            parsed_data['receiver'] = user.first_name

        # Сохраняем в БД
        session = self.db.get_session()
        try:
            # Проверяем дубликаты
            existing = session.query(GasRecord).filter_by(message_id=parsed_data['message_id']).first()
            if existing:
                await update.message.reply_text("⚠️ Это сообщение уже было обработано")
                return

            record = GasRecord(**parsed_data)
            session.add(record)
            session.commit()
            session.refresh(record)

            # Ищем связанные записи ТОЛЬКО если есть комната
            if record.room:
                linked_record = self.parser.find_linked_record(session, record)
                if linked_record:
                    if record.amount and not record.quantity:
                        linked_record.linked_record_id = record.id
                    elif record.quantity and record.quantity < 0:
                        record.linked_record_id = linked_record.id
                    session.commit()

        finally:
            session.close()

        # Форматируем сообщение для рассылки
        formatted_message = self.format_record(record)
        notification = f"💬 {user.first_name}: {text}\n\n{formatted_message}"

        # Рассылаем уведомления всем пользователям
        await self.notify_all_users(context, notification, exclude_user_id=user.id)

        # Подтверждение отправителю
        balance_27, balance_12 = self.db.get_balance()
        response = f"✅ Запись добавлена!\n\n📊 Текущий остаток: {balance_27}" # (27л), {balance_12} (12л)"
        await update.message.reply_text(response)

    async def handle_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команды в канале"""
        message = update.channel_post or update.message
        if not message:
            return

        command = message.text.split()[0].lower()

        if command == '/get_channel_id':
            await self.get_channel_id_command(update, context)

    async def notify_all_users(self, context, message, exclude_user_id=None):
        """Рассылает сообщение всем пользователям кроме исключенного"""
        for user_id in self.allowed_user_ids:
            if user_id == exclude_user_id:
                continue
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    def is_valid_gas_message(self, text):
        """Проверяет, является ли сообщение валидной записью о газе"""
        # Парсим сообщение для проверки
        parsed_data = self.parser.parse_message(text)

        has_quantity = parsed_data['quantity'] is not None
        has_amount = parsed_data['amount'] is not None
        has_room = parsed_data['room'] is not None

        # Валидные случаи:

        # 1. Любое сообщение с количеством баллонов (приход/расход)
        if has_quantity:
            return True

        # 2. Любое сообщение с суммой денег (оплата/предоплата)
        if has_amount:
            return True

        # 3. Если есть только комната - это запрос истории
        if has_room and not (has_quantity or has_amount):
            return False

        return False

    async def get_channel_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения ID канала"""
        # Определяем, откуда пришло сообщение - из канала или личного чата
        if update.channel_post:
            message_obj = update.channel_post
        elif update.message:
            message_obj = update.message
        else:
            return  # Если нет сообщения, выходим

        chat = message_obj.chat

        if chat.type in ['channel', 'group', 'supergroup']:
            message = (
                f"📋 Информация о чате:\n"
                f"ID: `{chat.id}`\n"
                f"Название: {chat.title}\n"
                f"Тип: {chat.type}\n"
                f"Username: @{chat.username or 'нет'}"
            )

            # Если это канал, предлагаем сохранить ID
            if chat.type == 'channel':
                message += f"\n\n💡 Добавьте в .env файл:\nTELEGRAM_CHANNEL_ID={chat.id}"

            # Отправляем ответ в тот же чат
            await context.bot.send_message(
                chat_id=chat.id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        else:
            await context.bot.send_message(
                chat_id=chat.id,
                text="Эта команда работает только в каналах и группах. "
                     "Добавьте бота в канал и используйте команду там."
            )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user

        if not await self.is_user_allowed(user.id):
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту.\n"
                "Обратитесь к администратору."
            )
            return

        await update.message.reply_text(
            "Привет! Я бот для учета газовых баллонов.\n\n"
            "Команды:\n"
            "/balance - текущий остаток баллонов\n"
            "/last - последние движения\n"
            "/my_id - показать мой ID\n"
            "Напишите номер комнаты (например, 1.01) для просмотра истории\n\n"
            "Примеры записей:\n"
            "+5 27 - приход баллонов\n"
            "-1 1.01 - расход баллона\n"
            "-1 1.02 1000 Сергей - расход с оплатой\n"
            "1000 3.3 - оплата от комнаты 3.3 (получатель - я)\n"
            "1000 3.3 Валя - оплата от комнаты 3.3 Вале\n"
            "3.3 1000 - альтернативный формат оплаты"
        )

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает текущий остаток баллонов"""
        balance_27, balance_12 = self.db.get_balance()

        message = f"📊 Текущий остаток:\n"
        if balance_27 > 0:
            message += f"• {balance_27} баллон(ов) 27л\n"
        if balance_12 > 0:
            message += f"• {balance_12} баллон(ов) 12л\n"

        if balance_27 <= 0 and balance_12 <= 0:
            message += "• Нет баллонов в наличии"

        await update.message.reply_text(message)

    async def last_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает последние движения"""
        session = self.db.get_session()
        try:
            records = session.query(GasRecord).order_by(GasRecord.id.desc()).limit(10).all()

            if not records:
                await update.message.reply_text("Нет записей о движениях")
                return

            message = "📈 Последние движения:\n\n"
            for record in reversed(records):
                message += self.format_record(record) + "\n"

            # Добавляем текущий баланс
            balance_27, balance_12 = self.db.get_balance()
            message += f"\n📊 Текущий остаток: {balance_27}" # (27л), {balance_12} (12л)"

            await update.message.reply_text(message)
        finally:
            session.close()

    def format_record(self, record: GasRecord) -> str:
        """Форматирует запись для отображения"""
        parts = []

        if record.quantity:
            sign = "+" if record.quantity > 0 else ""
            parts.append(f"{sign}{record.quantity} баллон(ов) {record.capacity}л")

        if record.room:
            parts.append(f"комната {record.room}")

        if record.amount:
            parts.append(f"{record.amount} руб")

        if record.receiver:
            parts.append(f"получил {record.receiver}")

        if record.comments:
            parts.append(f"({record.comments})")

        return " | ".join(parts)

    async def handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает сообщения в канале"""
        message = update.channel_post or update.message
        if not message:
            return

        # Парсим сообщение
        parsed_data = self.parser.parse_message(message.text)
        parsed_data['message_id'] = message.message_id
        parsed_data['date'] = message.date

        # Вся работа в одной сессии
        session = self.db.get_session()
        try:
            # Проверяем, существует ли уже запись
            existing = session.query(GasRecord).filter_by(message_id=parsed_data['message_id']).first()
            if existing:
                record = existing
            else:
                record = GasRecord(**parsed_data)
                session.add(record)
                session.commit()
                session.refresh(record)  # Обновляем объект после коммита

            # Ищем связанные записи (теперь record привязан к сессии)
            linked_record = self.parser.find_linked_record(session, record)
            if linked_record:
                if record.amount and not record.quantity:
                    linked_record.linked_record_id = record.id
                elif record.quantity and record.quantity < 0:
                    record.linked_record_id = linked_record.id
                session.commit()
        finally:
            session.close()

        # Публикуем обновленный баланс
        balance_27, balance_12 = self.db.get_balance()
        balance_message = f"📊 Остаток: {balance_27} баллон(ов) 27л"
        if balance_12 > 0:
            balance_message += f", {balance_12} баллон(ов) 12л"

        await context.bot.send_message(
            chat_id=message.chat_id,
            text=balance_message
        )

    async def handle_private_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает личные сообщения боту"""
        text = update.message.text.strip()

        # Проверяем, является ли текст номером комнаты
        if re.match(r'^\d+\.\d+$', text) or text.lower() in ['дом', 'домой']:
            room = text.lower() if text.lower() in ['дом', 'домой'] else text
            await self.show_room_history(update, room)
        else:
            await update.message.reply_text(
                "Не понимаю команду. Используйте:\n"
                "/balance - остаток баллонов\n"
                "/last - последние движения\n"
                "Или напишите номер комнаты для просмотра истории"
            )

    async def show_room_history(self, update: Update, room: str):
        """Показывает историю по комнате"""
        records = self.db.get_records_by_room(room, limit=15)

        if not records:
            await update.message.reply_text(f"Нет записей для комнаты {room}")
            return

        message = f"📋 История по комнате {room}:\n\n"
        total_owed = 0
        total_paid = 0

        for record in reversed(records):
            message += self.format_record(record) + "\n"

            if record.quantity and record.quantity < 0:
                total_owed += abs(record.quantity)
            if record.amount:
                total_paid += record.amount

        message += f"\nИтого: взято {total_owed} баллон(ов), оплачено {total_paid} руб"

        await update.message.reply_text(message)

    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        self.application.run_polling()


if __name__ == '__main__':
    bot = GasBot()
    bot.run()