FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for PyQt5 and X11
RUN apt-get update && apt-get install -y \
    python3-pyqt5 \
    x11-apps \
    xvfb \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libegl1 \
    libgl1 \
    libglib2.0-0 \
    libxrender1 \
    libfontconfig1 \
    libxcb-sync1 \
    libxcb-shm0 \
    libxi6 \
    libsm6 \
    libxext6 \
    libx11-6 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

CMD ["python3", "main.py"]