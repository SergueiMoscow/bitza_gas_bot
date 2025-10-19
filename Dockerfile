FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml poetry.lock ./
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without test && \
    pip cache purge
COPY src/ ./src/
CMD ["python", "-m", "src.bot"]