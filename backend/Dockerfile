FROM python:3.12-slim
WORKDIR /app

# Build context is repo root (see deploy.yml)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jobs/pacs008-generator/pacs008_generator/ pacs008_generator/
COPY jobs/pacs008-generator/error_catalog.yaml .
COPY backend/ .

EXPOSE 8080
CMD ["sh", "-c", "python seed_db.py && uvicorn main:app --host 0.0.0.0 --port 8080"]
