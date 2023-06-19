# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt
RUN apt-get update && apt-get install -y poppler-utils

# Copy the rest of the application code
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5430

VOLUME /app/cert
VOLUME /app/data

# Run the command to start the Flask application
#CMD ["flask", "run", "--host=0.0.0.0"]
CMD ["python", "app.py"]