# Cloud-Run-ready Image fuer die Streamlit Self-Service UI.
# Lokal: docker build -t gro-reporting . && docker run -p 8080:8080 --env-file .env gro-reporting
FROM python:3.12-slim

# WeasyPrint System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY clients ./clients
COPY assets ./assets
COPY app.py ./
COPY .streamlit ./.streamlit
COPY static ./static

ENV PORT=8080

CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
