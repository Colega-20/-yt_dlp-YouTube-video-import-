# Usa una imagen base que soporte Python o el entorno que necesites
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Instala ffmpeg y otras dependencias necesarias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia los archivos de tu proyecto al contenedor
COPY . .

# Instala las dependencias de Python (si es un proyecto de Python)
RUN pip install --no-cache-dir -r requirements.txt

# Expón el puerto que necesita tu aplicación
EXPOSE 8000

# Comando para ejecutar tu aplicación
CMD ["python", "app.py"]
