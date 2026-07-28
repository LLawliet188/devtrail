FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# One worker with a few threads: the database is SQLite, so several
# processes writing to the same file would only fight each other.
CMD ["sh", "-c", "gunicorn wsgi:application --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 60"]
