# 1. Usamos una versión ligera de Python
FROM python:3.12-slim

# 2. Configuraciones para que Python no guarde archivos basura
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Creamos una carpeta de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalamos dependencias del sistema necesarias para Postgres
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiamos tus requerimientos e instalamos las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos todo tu código al contenedor
COPY . .

# 7. Recolectamos los archivos estáticos (CSS, JS) en una sola carpeta
# Usamos variables falsas solo para que este comando no falle al construir
RUN DATABASE_URL="sqlite:///" SECRET_KEY="dummy-secret-key-build" python manage.py collectstatic --noinput --settings=core.settings

# 8. Cloud Run nos dará un puerto, por defecto 8080
EXPOSE 8080

# 9. El comando que arranca tu app.
# Usamos 'gunicorn' con 'uvicorn' para soportar tus websockets (Channels)
CMD ["gunicorn", "core.asgi:application", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]