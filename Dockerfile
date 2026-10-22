# One image for the whole app: the interface is built here and served by the API (app.web:root).
FROM node:22-slim AS interface
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY data data
COPY --from=interface /build/dist frontend/dist
WORKDIR /app/backend
# Render sets PORT; locally it defaults to 8000
CMD ["sh", "-c", "uvicorn app.web:root --host 0.0.0.0 --port ${PORT:-8000}"]
