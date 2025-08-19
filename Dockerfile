# Usamos Python 3.12 para wheels precompilados de pandas/numpy
FROM python:3.12-slim

# Mejoras de runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ONLY_BINARY=:all:      
    

WORKDIR /app

# Copiamos requirements primero para cache
COPY requirements.txt .

# Instalar dependencias Python
RUN python -V && pip -V && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiamos el resto del proyecto
COPY . .

EXPOSE 8000
ENV PORT=8000

# Arranque (Render define $PORT)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
