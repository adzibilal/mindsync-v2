FROM python:3.11-slim

WORKDIR /app

# Install system deps for PyMuPDF + Tesseract OCR (Indonesian + English)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-ind \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
