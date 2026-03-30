FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/server.py .
COPY frontend/ /app/frontend/

CMD ["python", "server.py"]
