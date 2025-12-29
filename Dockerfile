# --- Stage 1: Builder ---
# Use an official Python image as a base for building and installing dependencies
FROM python:3.11-slim-bullseye AS builder

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV APP_HOME=/app

# Create and set the working directory
WORKDIR $APP_HOME

# Copy only the requirements file first to take advantage of Docker's cache
COPY requirements.txt .

# Install dependencies. Use --no-cache-dir to keep the image small.
RUN pip install --no-cache-dir --upgrade pip
# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
# Use a smaller base image for the final production environment
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED 1
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Copy the installed dependencies and the application code from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . $APP_HOME

# Expose the port Uvicorn will run on
EXPOSE 8000

# Command to run the application (Uvicorn)
# Use gunicorn with uvicorn workers in a production environment for better stability/performance
# The command below is a standard production run command.
CMD ["gunicorn", "src.main:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker"]
# Alternatively, for simple testing/reload:
# CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]