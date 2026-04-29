FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create credentials directory
RUN mkdir -p ~/.insighta

# Set default API URL
ENV INSIGHTA_API_URL=http://api:8000

# Use the CLI as entrypoint
ENTRYPOINT ["python", "-m", "insighta_cli.main"]
CMD ["--help"]
