from flask import Flask, request, render_template, send_from_directory, jsonify, send_file
import yt_dlp
import os
import threading
import time
import re
import emoji

app = Flask(__name__)

# Carpeta donde se guardarán los videos descargados
DOWNLOAD_FOLDER = "./descargas"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
# Configurar Flask para servir archivos estáticos desde la carpeta de descargas
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
# Diccionario para rastrear el último acceso a cada archivo
last_access_times = {}
# Tiempo de inactividad para eliminar archivos (en segundos)
DELETE_AFTER = 300  # 5 minutos
# Bloqueo para evitar problemas de concurrencia
lock = threading.Lock()

def download_video(video_url, quality):
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'

    try:
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'format': quality,
            'merge_output_format': 'mp4',
            'user_agent': user_agent,
            'http_headers': {'User-Agent': user_agent}
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_path = ydl.prepare_filename(info)
            base_path = os.path.splitext(file_path)[0]
            file_path = f"{base_path}.mp4"
            # Registrar el acceso al archivo
            with lock:
                last_access_times[file_path] = time.time()

            return file_path
    except Exception as e:
        return str(e)


def clean_filename(filename):
    # Eliminar emojis
    filename = emoji.replace_emoji(filename, replace=" ")  
    # Reemplazar # y cualquier otro carácter especial no deseado por espacios
    filename = re.sub(r'[#]', ' ', filename)  
    # Eliminar espacios repetidos y recortar
    return re.sub(r'\s+', ' ', filename).strip()


@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/download_video', methods=['POST'])
def download_video_route():
    video_url = request.form.get('video_url')
    quality = request.form.get('quality', 'best')

    if not video_url:
        return jsonify({"error": "No se proporcionó una URL"}), 400

    # Descargar el video en un hilo separado
    file_path = download_video(video_url, quality)
    # Esperar hasta que el archivo realmente exista y tenga contenido
    max_wait_time = 60  # Segundos máximo de espera
    start_time = time.time()

    while not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        time.sleep(1)
        
        if time.time() - start_time > max_wait_time:
            return jsonify({"error": "La descarga tardó demasiado en completarse"}), 500

    # Validar si el archivo se generó correctamente antes de continuar
    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
      filename = os.path.basename(file_path)
      clean_name = clean_filename(filename)  # Aplicar limpieza
      # Renombrar el archivo con el nuevo nombre limpio
      new_file_path = os.path.join(os.path.dirname(file_path), clean_name)
      os.rename(file_path, new_file_path)  
      file_url = f"/statica/{clean_name}"
      # Registrar el acceso al archivo
      with lock:
        last_access_times[new_file_path] = time.time()
      return jsonify({"downloadUrl": file_url})

    return jsonify({"error": f"Error al descargar el video: {file_path}"}), 500
# Nueva ruta para servir archivos descargados
@app.route('/statica/<path:filename>', methods=['GET'])
def serve_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True, conditional=True)


def cleanup_files():
    """Elimina archivos que han estado inactivos por más de DELETE_AFTER segundos"""
    while True:
        time.sleep(10)  # Verificar cada 10 segundos

        with lock:
            current_time = time.time()
            files_to_delete = [file for file, last_access in last_access_times.items() if current_time - last_access > DELETE_AFTER]

            for file in files_to_delete:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        print(f"Archivo eliminado por inactividad: {file}")
                        del last_access_times[file]
                except Exception as e:
                    print(f"Error al eliminar {file}: {e}")


# Iniciar el hilo de limpieza en segundo plano
cleanup_thread = threading.Thread(target=cleanup_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5011, debug=True)
