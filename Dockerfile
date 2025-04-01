FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-external.txt dependencies.txt ./
# First try requirements-external.txt, then fallback to dependencies.txt if needed
RUN if [ -f "requirements-external.txt" ]; then \
        cp requirements-external.txt requirements.txt && \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir -r dependencies.txt; \
    fi

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p cache data

# Run the application
CMD ["python", "main.py"]