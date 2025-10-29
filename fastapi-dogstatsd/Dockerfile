FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn datadog

# Copy application code
COPY dogstatsd.py .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "dogstatsd:app", "--host", "0.0.0.0", "--port", "8000"]

