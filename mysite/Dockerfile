FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir aiogram==3.31.0 pypdf==6.7.4  python-dotenv

COPY mysite /app/mysite

CMD ["python", "-m", "mysite.db.continue_tutorial"]
