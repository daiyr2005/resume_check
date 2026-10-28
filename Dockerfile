FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir aiogram==3.31.0 aiohttp==3.14.3 pypdf==6.7.4

COPY mysite/db/continue_tutorial.py /app/continue_tutorial.py

CMD ["python", "continue_tutorial.py"]
