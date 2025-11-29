# 1. Use an official lightweight Python image
FROM python:3.9-slim

# 2. Install System Dependencies (Tesseract OCR & others)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /app

# 4. Copy requirements and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Command to run the app
# Render automatically assigns a PORT, usually 10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]