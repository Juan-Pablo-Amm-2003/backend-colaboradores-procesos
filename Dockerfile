# Usamos Python 3.12 para que haya wheels precompilados de pandas/numpy
FROM python:3.12-slim

# Ajustes recomendados para containers Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copiamos solo requirements primero para aprovechar la cache de Docker
COPY requirements.txt .

# Instalamos pip actualizado y dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Puerto por defecto; Render inyecta PORT y lo tomamos en el CMD
EXPOSE 8000
ENV PORT=8000

# Arranque de la API (toma PORT de entorno si existe, sino 8000)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
