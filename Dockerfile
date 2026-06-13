ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# opencv-python 运行时需要这些系统库。
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/Pikafish/Linux/pikafish-* /app/Pikafish/Android/pikafish-* || true \
    && mkdir -p /app/cache

EXPOSE 5050

CMD ["python", "run.py"]
