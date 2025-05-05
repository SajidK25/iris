# Use the official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Verify gunicorn is installed
RUN pip show gunicorn

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE $PORT

# Run the application
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:$PORT", "run:app"]