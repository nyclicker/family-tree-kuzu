FROM ubuntu:24.04
WORKDIR /app

# Install Python 3.12, pip, and browser dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    libatk1.0-0 libatk-bridge2.0-0 libnss3 libxss1 libxcb1 \
    libgtk-3-0 libpango-1.0-0 libgbm1 libxkbcommon0 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY app /app/app
COPY web /app/web
RUN pip install --no-cache-dir --break-system-packages .
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
