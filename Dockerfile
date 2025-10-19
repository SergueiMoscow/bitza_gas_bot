FROM python:3.12-slim

WORKDIR /app

# Обновляем пакеты и чистим кэш в одном RUN (Docker best practice)
RUN apt-get update && apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем Poetry и зависимости
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without test && \
    pip cache purge

# Копируем исходный код
COPY src/ ./src/

# Создаем точку входа
CMD ["python", "-m", "src.bot"]