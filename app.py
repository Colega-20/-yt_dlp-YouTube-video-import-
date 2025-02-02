from flask import Flask, request, render_template, send_file
import yt_dlp
import os
import threading
import time
os.system('chcp 65001')

app = Flask(__name__)

TEMP_DOWNLOAD_PATH = "./descargas"
os.makedirs(TEMP_DOWNLOAD_PATH, exist_ok=True)

def download_video(video_url, quality):
    try:
        ydl_opts = {
            'outtmpl': f'{TEMP_DOWNLOAD_PATH}/%(title)s.%(ext)s',
            'format': quality,
            'merge_output_format': 'mp4',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_path = ydl.prepare_filename(info)
            base_path = os.path.splitext(file_path)[0]
            file_path = f"{base_path}.mp4"
            return file_path
    except Exception as e:
        return str(e)

def delete_file_later(file_path, delay=10, retry_delay=15, max_retries=40):
    time.sleep(delay)
    retries = 0
    
    while retries < max_retries:
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Archivo eliminado: {file_path}")
                return  # Salir de la función si se elimina el archivo
        except PermissionError:
            print(f"Error de permiso al intentar eliminar el archivo: {file_path}. Reintentando en {retry_delay} segundos...")
            time.sleep(retry_delay)  # Esperar antes de reintentar
            retries += 1
    
    print(f"No se pudo eliminar el archivo después de {max_retries} intentos: {file_path}")

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/download_video', methods=['POST'])
def download_video_route():
    video_url = request.form.get('video_url')
    quality = request.form.get('quality', 'best')
    
    if not video_url:
        return "No se proporcionó una URL", 400

    file_path = download_video(video_url, quality)
    if os.path.isfile(file_path):
        threading.Thread(target=delete_file_later, args=(file_path,)).start()
        return send_file(file_path, as_attachment=True)
    else:
        return f"Error al descargar el video: {file_path}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5011))
    app.run(host="0.0.0.0", port=port, debug=True)
