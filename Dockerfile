FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && mv /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .

CMD ["python", "bot.py"]
