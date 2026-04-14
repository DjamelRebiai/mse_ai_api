FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    --no-install-recommends && \
    # We still need some basic X11 libs for Chromium even in headless mode
    apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libpangocairo-1.0-0 libgtk-3-0 \
    fonts-liberation fonts-noto-color-emoji fonts-arabeyes \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY --chown=user . /app

# Run uvicorn directly on port 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]