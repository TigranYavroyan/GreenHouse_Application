#!/bin/bash

echo "Starting Greenhouse Automation System..."

# Make sure X11 is running for GUI (Linux)
if [ "$(uname)" == "Linux" ]; then
    echo "Setting up X11 display..."
    xhost +local:docker
fi

# Start all services
docker-compose up -d

echo "Services starting..."
echo "Backend API: http://localhost:3000"
echo "RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "Redis: localhost:6379"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
sleep 10

# Check health
curl -f http://localhost:3000/health && echo "Backend is healthy!" || echo "Backend health check failed"

echo "Use 'docker-compose logs -f' to view logs"
echo "Use 'docker-compose down' to stop services"