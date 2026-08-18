FROM python:3.11-slim

# Install system dependencies (ffmpeg is crucial for video/audio processing)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
