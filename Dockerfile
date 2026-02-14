FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml /app/
COPY app /app/app
COPY web /app/web
COPY data /app/data
RUN pip install --no-cache-dir -e .
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
