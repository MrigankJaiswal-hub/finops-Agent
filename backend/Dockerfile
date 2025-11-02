# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps (optional: lib for pandas/numpy)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# make sure app listens on 0.0.0.0:8000
ENV PORT=8000

# (Optional) speed: compile py files
RUN python -m compileall .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
