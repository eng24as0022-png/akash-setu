FROM python:3.12-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV HOST=0.0.0.0

# Copy application files
COPY . /app

# Expose container port
EXPOSE 8080

# Launch Akash Setu
CMD ["python", "server.py"]
