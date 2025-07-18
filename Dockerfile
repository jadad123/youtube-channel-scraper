# Use an official Python image
FROM python:3.9-slim-buster

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libwebkit2gtk-4.0-37 \
    libgdk-pixbuf2.0-0 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libglib2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxkbcommon0 \
    libharfbuzz0b \
    libfontconfig1 \
    libfreetype6 \
    libsqlite3-0 \
    libnss3 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libegl1 \
    libgbm1 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer1.0-0 \
    libgtk-3-0 \
    libice6 \
    libmutter-10-0 \
    libsm6 \
    libsoup2.4-1 \
    libwayland-client0 \
    libwayland-egl1 \
    libwayland-server0 \
    libwpewebkit-1.0-1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence6 \
    libxxf86vm1 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
