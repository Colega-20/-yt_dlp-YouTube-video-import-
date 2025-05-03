
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
import subprocess
import os
import shutil
from urllib.parse import quote  # Importar quote para codificar el nombre del archivo

# Crear una instancia de la aplicación Flask
app = Flask(__name__)

# Directorio donde se almacenarán los archivos descargados
DOWNLOAD_FOLDER = "downloads"
# Crea el directorio si no existe
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Ruta para la página principal
@app.route("/")
def home():
    # Renderiza el archivo HTML `index.html` como la página principal
    return render_template("index.html")

# Ruta para manejar la descarga de audio
@app.route("/download", methods=["POST"])
def download_audio():
    # Obtiene los datos enviados desde el cliente en formato JSON
    data = request.get_json()
    # Extrae la URL de YouTube del JSON
    youtube_url = data.get("url")

    # Verifica que se haya proporcionado una URL
    if not youtube_url:
        # Devuelve un error 400 si no hay URL
        return jsonify({"error": "No URL provided"}), 400

    # Comando para descargar el audio utilizando yt-dlp
    command = [
        'yt-dlp',  # Herramienta para descargar videos o audios de YouTube y otros servicios
        '--cookies', 'cookies.txt',  # 👈 esta línea
        '-f', 'bestaudio[ext=m4a]/best',  # Selecciona el mejor formato de audio disponible
        '--extract-audio',  # Extrae solo el audio
        '--audio-format', 'mp3',  # Convierte el audio a formato MP3
        '--audio-quality', '320K',  # Calidad de audio a 320 kbps
        '--output', os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),  # Define el nombre y la ubicación del archivo
        youtube_url  # URL del video de YouTube
    ]

    try:
        # Ejecuta el comando para descargar el audio
        subprocess.run(command, check=True)
        
        # Encuentra el archivo descargado más reciente en la carpeta `downloads`
        downloaded_file = max(
            (os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)),
            key=os.path.getctime  # Ordena por la fecha de creación
        )

        # Verifica cuántos archivos hay en la carpeta
        files_in_folder = os.listdir(DOWNLOAD_FOLDER)
        if len(files_in_folder) > 2:  # Cambia este número según el límite deseado
            # Encuentra el archivo más antiguo en la carpeta
            oldest_file = min(
                (os.path.join(DOWNLOAD_FOLDER, f) for f in files_in_folder),
                key=os.path.getctime  # Ordena por fecha de creación
            )
            # Elimina el archivo más antiguo para mantener el límite
            os.remove(oldest_file)

        # Codifica el nombre del archivo para que sea seguro en la URL
        return jsonify({"download_link": f"/files/{quote(os.path.basename(downloaded_file))}"})
    except subprocess.CalledProcessError as e:
        # Devuelve un error si el comando para descargar falló
        return jsonify({"error": f"Download failed: {str(e)}"}), 500
    except ValueError:
        # Devuelve un error si no se descargaron archivos
        return jsonify({"error": "No files downloaded"}), 500

# Ruta para servir archivos descargados al cliente
@app.route("/files/<path:filename>", methods=["GET"])
def get_file(filename):
    # Envía el archivo solicitado como una descarga
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

# Punto de entrada de la aplicación
if __name__ == "__main__":
    # Define el puerto en el que se ejecutará la aplicación (por defecto 5000)
    port = int(os.environ.get("PORT", 5000))  # Railway asigna el puerto dinámicamente
    # Inicia la aplicación Flask en el host 0.0.0.0 (escucha en todas las interfaces de red)
    app.run(host="0.0.0.0", port=port, debug=True)
