FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app app
COPY backend/tests tests
COPY backend/check_data.py backend/pytest.ini ./
COPY --from=web /web/dist static
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
