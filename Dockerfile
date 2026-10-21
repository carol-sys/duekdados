# Imagem para Render, Hugging Face Spaces ou qualquer serviço com Docker
FROM python:3.12-slim

# Chromium + driver para a coleta com Selenium
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium chromium-driver fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8501 PYTHONUNBUFFERED=1
EXPOSE 8501
CMD streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true
