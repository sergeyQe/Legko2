FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1

WORKDIR /app

# зависимости ставятся отдельным слоем: он пересобирается только при изменении requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini docker-entrypoint.sh ./

# на случай Windows-переводов строк в скрипте; запуск не от root
RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && chmod +x docker-entrypoint.sh \
    && useradd --create-home --shell /usr/sbin/nologin legko2 \
    && chown -R legko2:legko2 /app
USER legko2

EXPOSE 8000
CMD ["./docker-entrypoint.sh"]
