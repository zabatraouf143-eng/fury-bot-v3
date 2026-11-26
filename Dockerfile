FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    apksigner \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar -O /usr/local/bin/apktool.jar \
    && printf '#!/bin/sh\nexec java -Xmx350m -jar /usr/local/bin/apktool.jar "$@"\n' > /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "bot.py"]
