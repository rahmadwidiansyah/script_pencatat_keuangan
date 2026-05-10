FROM python:3.9-slim

ENV TZ=Asia/Jakarta
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser
USER appuser

EXPOSE 3987


# Ubah baris CMD terakhir menjadi ini agar uvicorn dijalankan via module 
# dan mendukung signal terminasi Docker dengan lebih baik
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3987", "--workers", "2"]