# Usa una imagen base con Python o el entorno necesario
FROM python:3.13-slim

# Establece el directorio de trabajo en la raíz del contenedor
WORKDIR /

# Instala ffmpeg y otras dependencias necesarias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia los archivos del proyecto al directorio raíz
COPY . /

# Instala las dependencias de Python desde requirements.txt, si es un proyecto de Python
RUN pip install --no-cache-dir -r requirements.txt

# Expón el puerto si tu aplicación lo requiere
EXPOSE 5000

# Define el comando por defecto para ejecutar tu aplicación
CMD ["python", "app.py"]
