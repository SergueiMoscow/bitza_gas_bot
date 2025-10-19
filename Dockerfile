FROM python:3.12-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем Poetry и зависимости
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction

# Копируем исходный код
COPY src/ ./src/

# Создаем точку входа
CMD ["python", "-m", "src.bot"]