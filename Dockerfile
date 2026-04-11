FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker/entrypoint.sh /app/docker/cmd-web.sh

RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    SECRET_KEY=collectstatic-build-only-not-for-runtime \
    API_KEY_PEPPER=collectstatic-build-pepper-at-least-32-chars!! \
    ALLOWED_HOSTS=localhost,127.0.0.1 \
    python manage.py collectstatic --noinput

ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8000

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["./docker/cmd-web.sh"]
