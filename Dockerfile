# Use a stable Python base
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# We install: 
# - curl/git for cloning
# - ffmpeg for video processing
# - texlive for Manim/LaTeX math formulas
# - nodejs/npm for Remotion rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-latex-base \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to /app
WORKDIR /app

# Install Python dependencies
# We install docling and other core libs first to leverage Docker layer caching
RUN pip install --no-cache-dir \
    pydantic \
    python-dotenv \
    openai \
    docling \
    tqdm \
    pymupdf

# The rest of the dependencies are handled by the project's requirements
# We'll use a volume mount for the code, so we don't COPY it here.
# This allows "Hot Reloading" - edit code in Windows, run in Linux.

# Default command: keep the container alive so we can exec into it
CMD ["tail", "-f", "/dev/null"]
