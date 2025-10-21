#!/bin/bash

# Скрипт для запуска тестов Gas Bot

set -e  # Остановиться при ошибке

echo "🧪 Запуск тестов Gas Bot..."
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверяем наличие pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest не установлен${NC}"
    echo "Установите зависимости: pip install -r requirements-test.txt"
    exit 1
fi

# Очищаем старые тестовые БД
echo -e "${BLUE}🧹 Очистка старых тестовых баз данных...${NC}"
rm -f test_gas.db test_gas.db-journal test*.db 2>/dev/null || true

# Запускаем тесты с разными опциями в зависимости от аргумента
case "${1:-all}" in
    "all")
        echo -e "${BLUE}📦 Запуск всех тестов...${NC}"
        pytest -v
        ;;
    "parser")
        echo -e "${BLUE}📝 Запуск тестов парсера...${NC}"
        pytest tests/test_parser.py -v
        ;;
    "bot")
        echo -e "${BLUE}🤖 Запуск тестов бота...${NC}"
        pytest tests/test_bot.py -v
        ;;
    "database"|"db")
        echo -e "${BLUE}💾 Запуск тестов базы данных...${NC}"
        pytest tests/test_database.py -v
        ;;
    "cov"|"coverage")
        echo -e "${BLUE}📊 Запуск тестов с покрытием кода...${NC}"
        pytest --cov=src --cov-report=html --cov-report=term-missing
        echo ""
        echo -e "${GREEN}✅ Отчет о покрытии сохранен в htmlcov/index.html${NC}"
        ;;
    "fast")
        echo -e "${BLUE}⚡ Быстрый запуск тестов (параллельно)...${NC}"
        pytest -n auto -v
        ;;
    "watch")
        echo -e "${BLUE}👀 Запуск в режиме наблюдения...${NC}"
        pytest-watch
        ;;
    "debug")
        echo -e "${BLUE}🐛 Запуск в режиме отладки...${NC}"
        pytest -vv -s --tb=long
        ;;
    "failed"|"lf")
        echo -e "${BLUE}🔄 Перезапуск последних упавших тестов...${NC}"
        pytest --lf -v
        ;;
    *)
        echo -e "${RED}❌ Неизвестная команда: $1${NC}"
        echo ""
        echo "Использование: ./run_tests.sh [команда]"
        echo ""
        echo "Доступные команды:"
        echo "  all       - Запустить все тесты (по умолчанию)"
        echo "  parser    - Только тесты парсера"
        echo "  bot       - Только тесты бота"
        echo "  db        - Только тесты базы данных"
        echo "  coverage  - Тесты с отчетом о покрытии"
        echo "  fast      - Быстрый параллельный запуск"
        echo "  debug     - Запуск с подробным выводом"
        echo "  failed    - Перезапуск последних упавших тестов"
        exit 1
        ;;
esac

# Проверяем код возврата
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Все тесты прошли успешно!${NC}"

    # Очищаем тестовые БД после успешного прохождения
    echo -e "${BLUE}🧹 Очистка тестовых баз данных...${NC}"
    rm -f test_gas.db test_gas.db-journal test*.db 2>/dev/null || true

    exit 0
else
    echo ""
    echo -e "${RED}❌ Некоторые тесты провалились${NC}"
    exit 1
fi