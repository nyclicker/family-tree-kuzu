#!/bin/bash
set -e

# Retry database connection with exponential backoff
MAX_RETRIES=10
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
  echo "Attempting database connection... (attempt $((RETRY + 1))/$MAX_RETRIES)"
  if python3 -c "import sqlalchemy; engine = sqlalchemy.create_engine('$DATABASE_URL'); engine.connect().close(); print('Database connected successfully')" 2>/dev/null; then
    break
  fi
  RETRY=$((RETRY + 1))
  if [ $RETRY -lt $MAX_RETRIES ]; then
    sleep $((2 ** RETRY))  # Exponential backoff
  fi
done

if [ $RETRY -eq $MAX_RETRIES ]; then
  echo "Failed to connect to database after $MAX_RETRIES attempts"
  exit 1
fi

# Start the server
echo "Starting uvicorn server..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
