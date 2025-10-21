# 🧪 Руководство по тестированию Gas Bot

## 📦 Установка зависимостей

```bash
pip install -r requirements-test.txt
```

## 🏗️ Структура тестов

```
tests/
├── conftest.py              # Фикстуры и общие настройки
├── test_parser.py           # Тесты парсера сообщений
├── test_bot.py              # Тесты обработки сообщений ботом
└── test_database.py         # Тесты работы с базой данных
```

## 🚀 Запуск тестов

### Запустить все тесты
```bash
pytest
```

### Запустить конкретный файл
```bash
pytest tests/test_parser.py
```

### Запустить конкретный тест
```bash
pytest tests/test_parser.py::TestMessageParser::test_parse_message
```

### Запустить тесты с покрытием кода
```bash
pytest --cov=src --cov-report=html
```
Отчет будет в `htmlcov/index.html`

### Запустить тесты параллельно (быстрее)
```bash
pytest -n auto
```

### Запустить только быстрые тесты
```bash
pytest -m "not slow"
```

## 🔧 Основные фикстуры

### `test_db`
Создает чистую тестовую БД для каждого теста
```python
def test_something(test_db):
    record = test_db.add_record({...})
    assert record is not None
```

### `parser`
Возвращает экземпляр MessageParser
```python
def test_parsing(parser):
    result = parser.parse_message("+5")
    assert result['quantity'] == 5
```

### `mock_update` и `mock_context`
Моки объектов Telegram для тестирования бота
```python
async def test_bot(gas_bot, mock_update, mock_context):
    await gas_bot.handle_gas_message(mock_update, mock_context)
```

### `sample_gas_records`
Набор готовых тестовых записей в БД
```python
def test_with_data(test_db, sample_gas_records):
    records = test_db.get_records_by_room('2.01')
    assert len(records) == 1
```

## 📝 Примеры тестов

### Простой тест парсинга
```python
def test_parse_arrival(parser):
    result = parser.parse_message("+5 27")
    assert result['quantity'] == 5
    assert result['capacity'] == 27
```

### Параметризованный тест
```python
@pytest.mark.parametrize("text,expected_quantity", [
    ("+5", 5),
    ("+10", 10),
    ("-1", -1),
])
def test_quantities(parser, text, expected_quantity):
    result = parser.parse_message(text)
    assert result['quantity'] == expected_quantity
```

### Асинхронный тест бота
```python
@pytest.mark.asyncio
async def test_process_message(gas_bot, mock_update, mock_context):
    mock_update.message.text = "+5"
    await gas_bot.process_gas_message(
        mock_update, mock_context, "+5", 
        mock_update.message.from_user
    )
    
    record = gas_bot.db.get_last_record()
    assert record.quantity == 5
```

### Тест с проверкой вызовов
```python
@pytest.mark.asyncio
async def test_reply_sent(gas_bot, mock_update, mock_context):
    mock_update.message.text = "+5"
    
    await gas_bot.handle_gas_message(mock_update, mock_context)
    
    # Проверяем что был вызван reply_text
    mock_update.message.reply_text.assert_called()
```

## 🎯 Сценарии для тестирования

### Предоплата → Взятие газа
```python
@pytest.mark.asyncio
async def test_prepayment_flow(gas_bot, mock_update, mock_context):
    user = mock_update.message.from_user
    
    # 1. Предоплата
    mock_update.message.text = "1000 2.01 Иван"
    mock_update.message.message_id = 1
    await gas_bot.process_gas_message(mock_update, mock_context, 
                                     "1000 2.01 Иван", user)
    
    # 2. Взятие газа
    mock_update.message.text = "-1 2.01"
    mock_update.message.message_id = 2
    await gas_bot.process_gas_message(mock_update, mock_context, 
                                     "-1 2.01", user)
    
    # Проверка связывания
    prepayment = gas_bot.db.get_record_by_message_id(1)
    assert prepayment.quantity == -1
    assert prepayment.amount == 1000
```

## ⚠️ Важные правила

### ✅ DO (Делайте так)
- Всегда используйте фикстуру `test_db` для работы с БД
- Параметризуйте тесты для проверки множества сценариев
- Проверяйте как успешные, так и ошибочные сценарии
- Используйте осмысленные имена тестов
- Изолируйте тесты друг от друга

### ❌ DON'T (Не делайте так)
- Не используйте production БД в тестах
- Не полагайтесь на порядок выполнения тестов
- Не создавайте зависимости между тестами
- Не забывайте про async/await для асинхронных функций
- Не пишите тесты без assert

## 🐛 Отладка тестов

### Вывести больше информации
```bash
pytest -vv
```

### Показать print() в тестах
```bash
pytest -s
```

### Остановиться на первой ошибке
```bash
pytest -x
```

### Запустить последние упавшие тесты
```bash
pytest --lf
```

### Показать traceback полностью
```bash
pytest --tb=long
```

### Запустить в режиме отладки
```bash
pytest --pdb
```

## 📊 Метрики покрытия

Стремимся к покрытию:
- **Parser**: 100% (критический компонент)
- **Database**: 95%+ (важные операции)
- **Bot handlers**: 80%+ (основная логика)

Проверить покрытие:
```bash
pytest --cov=src --cov-report=term-missing
```

## 🔄 CI/CD

В GitHub Actions можно добавить:
```yaml
- name: Run tests
  run: |
    pip install -r requirements-test.txt
    pytest --cov=src --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## 📚 Дополнительные ресурсы

- [Pytest документация](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Python Mock](https://docs.python.org/3/library/unittest.mock.html)

## 🆘 Частые проблемы

### Проблема: Тесты падают с ошибкой "database is locked"
**Решение**: Убедитесь что закрываете сессии в finally блоках

### Проблема: AsyncioRuntimeError
**Решение**: Добавьте декоратор `@pytest.mark.asyncio` к асинхронным тестам

### Проблема: Тесты используют production БД
**Решение**: Проверьте что в названии БД есть слово 'test'

### Проблема: Фикстуры не находятся
**Решение**: Убедитесь что conftest.py находится в корне папки tests