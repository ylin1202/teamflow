FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 防止 Python 產生 .pyc 與開啟 stdout 無緩衝
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安裝系統層級依賴 (MySQL 相關編譯套件)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 套件
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案程式碼
COPY . /app/