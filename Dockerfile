# Use an official Python image
FROM python:3.9-slim-bullseye

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y     build-essential     libnss3     libatk-bridge2.0-0     libxkbcommon0     libgbm1     libasound2     libgtk-3-0     libxss1     libdrm2     libxcomposite1     libxrandr2     libxi6     libxfixes3     libxext6     libxrender1     libcups2     libfontconfig1     libfreetype6     libglib2.0-0     libjpeg-dev     libpng-dev     libwebp-dev     libtiff-dev     xdg-utils     --no-install-recommends &&     rm -rf /var/lib/apt/lists/*

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
