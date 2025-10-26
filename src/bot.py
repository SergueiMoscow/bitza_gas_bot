import os
import re
import sys
from datetime import datetime

from telegram import Update, InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv

from src.config import WEB_APP_DOMAIN

sys.path.append(os.path.dirname(__file__))

from database import Database
from parser import MessageParser
from models import GasRecord

# Загрузка переменных окружения
load_dotenv()

import logging

# Отключаем логи httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Оставляем только важные логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def _setup_commands(application: Application):
    """Устанавливает список команд в меню Telegram."""
    commands = [
        BotCommand("balance", "остаток"),
        BotCommand("last", "последние"),
        BotCommand("debts", "долги (app)"),
        BotCommand("web_last", "последние (app)"),
        BotCommand("web_debts", "долги (app)"),
        BotCommand("start", "начать"),
    ]

    # application.bot - это объект Bot, который используется для вызова методов API
    await application.bot.set_my_commands(commands)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    logging.info("Список команд Telegram меню успешно установлен.")


class GasBot:
    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        self.application.run_polling()

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

        self.application = Application.builder().token(self.token).post_init(_setup_commands).build()

        # Добавляем обработчик ошибок
        self.application.add_error_handler(self.error_handler)

        # mini apps handlers
        self.application.add_handler(CommandHandler("web_last", self.web_last_command))
        self.application.add_handler(CommandHandler("web_debts", self.web_debts_command))

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


    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logging.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

        # Если это конфликт с другим экземпляром бота - игнорируем
        if "Conflict: terminated by other getUpdates request" in str(context.error):
            logging.warning("Обнаружен конфликт с другим экземпляром бота. Проверьте, что запущен только один экземпляр.")
            return

        # Для других ошибок пытаемся уведомить пользователя
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз."
                )
            except:
                pass


    async def is_user_allowed(self, user_id: int) -> bool:
        """Проверяет, разрешен ли пользователь"""
        return user_id in self.allowed_user_ids


    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает ID пользователя (работает для всех, даже неавторизованных)"""
        user = update.message.from_user

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
        if parsed_data['amount'] and not parsed_data['receiver']:
            parsed_data['receiver'] = user.first_name

        session = self.db.get_session()
        try:
            # Проверяем дубликаты
            existing = session.query(GasRecord).filter_by(message_id=parsed_data['message_id']).first()
            if existing:
                await update.message.reply_text("⚠️ Это сообщение уже было обработано")
                return

            # Создаем запись
            record = GasRecord(**parsed_data)

            # Обрабатываем логику оплат и предоплат
            if record.room:
                # СЛУЧАЙ 1: Взятие газа (quantity < 0)
                if record.quantity and record.quantity < 0:
                    record.gas_taken_date = update.message.date
                    # Проверяем, была ли предоплата
                    prepayment = self.parser.find_prepayment_record(session, record.room)

                    if prepayment:
                        # Есть предоплата - заполняем данные о газе в запись с предоплатой
                        prepayment.quantity = record.quantity
                        prepayment.capacity = record.capacity
                        prepayment.gas_taken_date = update.message.date
                        if record.comments:
                            prepayment.comments = '/'.join([prepayment.comments, record.comments])
                        # Связываем записи
                        # record.linked_record_id = prepayment.id

                        session.add(prepayment)
                        session.commit()

                        await update.message.reply_text(
                            f"✅ Запись связана с предоплатой!\n"
                            f"Предоплата: {prepayment.amount} руб. от {prepayment.payment_date.strftime('%d.%m.%Y')}"
                        )
                        record = prepayment
                    elif record.amount:
                        # Взятие газа сразу с оплатой
                        record.payment_date = record.date
                        session.add(record)
                        session.commit()
                    else:
                        # Взятие газа без оплаты
                        session.add(record)
                        session.commit()

                # СЛУЧАЙ 2: Оплата без взятия газа (только amount, без quantity)
                elif record.amount and not record.quantity:
                    # Ищем неоплаченный расход газа
                    unpaid_gas = self.parser.find_unpaid_gas_record(session, record.room)

                    if unpaid_gas:
                        # Нашли неоплаченный газ - добавляем к нему оплату
                        unpaid_gas.amount = record.amount
                        unpaid_gas.receiver = record.receiver
                        unpaid_gas.payment_date = record.date
                        # Связываем записи
                        # record.linked_record_id = unpaid_gas.id

                        session.add(unpaid_gas)
                        session.commit()
                        record = unpaid_gas

                        await update.message.reply_text(
                            f"✅ Оплата добавлена к расходу от {unpaid_gas.date.strftime('%d.%m.%Y')}!"
                        )
                    else:
                        # Это предоплата
                        record.payment_date = record.date
                        session.add(record)
                        session.commit()

                        await update.message.reply_text("✅ Предоплата зарегистрирована!")
                else:
                    # Приход баллонов или другие случаи
                    session.add(record)
                    session.commit()
            else:
                # Нет комнаты (например, приход баллонов)
                session.add(record)
                session.commit()

            session.refresh(record)

        except Exception as e:
            session.rollback()
            logging.error(f"Error processing gas message: {e}", exc_info=True)
            await update.message.reply_text("❌ Ошибка при обработке сообщения")
            return
        finally:
            session.close()

        # Форматируем сообщение для рассылки
        formatted_message = self.format_record(record)
        notification = f"💬 {user.first_name}: {text}\n\n{formatted_message}"

        # Рассылаем уведомления всем пользователям
        await self.notify_all_users(context, notification, exclude_user_id=user.id)

        # Подтверждение отправителю (если еще не отправлено)
        balance_27, balance_12 = self.db.get_balance()
        # response = f"✅ Запись добавлена!\n\n📊 Текущий остаток: {balance_27}"
        response = f"📊 Текущий остаток: {balance_27}"
        try:
            await update.message.reply_text(response)
        except:
            pass  # Сообщение уже могло быть отправлено выше


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
        parsed_data = self.parser.parse_message(text)

        has_quantity = parsed_data['quantity'] is not None
        has_amount = parsed_data['amount'] is not None

        # Валидные случаи: есть количество баллонов ИЛИ есть сумма денег
        return has_quantity or has_amount

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
            message += f"\n📊 Текущий остаток: {balance_27}"

            await update.message.reply_text(message)
        finally:
            session.close()

    def format_record(self, record: GasRecord) -> str:
        """Форматирует запись для отображения из объекта GasRecord"""
        parts = []

        if record.quantity is not None:
            sign = "+" if record.quantity > 0 else ""
            capacity = record.capacity if record.capacity else 27
            parts.append(f"{sign}{record.quantity} баллон(ов) {capacity}л")

        if record.room:
            parts.append(f"комната {record.room}")

        if record.amount:
            parts.append(f"{record.amount} руб")

        if record.receiver:
            parts.append(f"получил {record.receiver}")

        if record.payment_date and record.amount:
            parts.append(f"оплачено {record.payment_date.strftime('%d.%m.%Y')}")

        if record.gas_taken_date and record.quantity and record.quantity < 0:
            parts.append(f"взято {record.gas_taken_date.strftime('%d.%m.%Y')}")

        if record.comments:
            parts.append(f"({record.comments})")

        return " | ".join(parts)


    async def show_room_history(self, update: Update, room: str):
        """Показывает историю по комнате"""
        normalized_room = MessageParser.normalize_room_number(room)
        records = self.db.get_records_by_room(normalized_room, limit=15)

        if not records:
            await update.message.reply_text(f"Нет записей для комнаты {normalized_room}")
            return

        message = f"📋 История по комнате {normalized_room}:\n\n"
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


    async def web_last_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открывает Web App с последними движениями"""
        user = update.message.from_user

        if not await self.is_user_allowed(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return

        web_app_url = f"{WEB_APP_DOMAIN}/web_last?user_id={user.id}"

        keyboard = [
            [InlineKeyboardButton("📊 Открыть последние движения", web_app=WebAppInfo(url=web_app_url))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📱 Откройте мини-приложение для просмотра последних движений:",
            reply_markup=reply_markup
        )

    async def web_debts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открывает Web App с долгами и висящими записями"""
        user = update.message.from_user

        if not await self.is_user_allowed(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return

        web_app_url = f"{WEB_APP_DOMAIN}/web_debts?user_id={user.id}"

        keyboard = [
            [InlineKeyboardButton("💰 Открыть долги и предоплаты", web_app=WebAppInfo(url=web_app_url))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📱 Откройте мини-приложение для просмотра долгов и предоплат:",
            reply_markup=reply_markup
        )


if __name__ == '__main__':
    bot = GasBot()
    bot.run()
