# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the Scrapy project into the container
COPY . .

# Copy the cron job file into the container
COPY scrapy_cron /etc/cron.d/scrapy_cron

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/scrapy_cron

# Apply cron job
RUN crontab /etc/cron.d/scrapy_cron

# Run the command on container startup
CMD ["cron", "-f"]

