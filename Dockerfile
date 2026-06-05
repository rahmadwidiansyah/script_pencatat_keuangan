# Menggunakan base image slim untuk efisiensi
FROM python:3.9-slim

ENV TZ=Asia/Jakarta
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies & timezone
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code
COPY . .

# Buat direktori storage untuk model agar tidak error saat load
RUN mkdir -p /app/storage/models && \
    useradd -m appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 3987

# Menggunakan mode production dengan workers
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3987", "--workers", "2"]