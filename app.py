from flask import Flask, request, render_template, send_file
import subprocess
import os
import threading
import time
import json
import re
import signal
from contextlib import contextmanager
import psutil

app = Flask(__name__)

TEMP_DOWNLOAD_PATH = "./descargas"
os.makedirs(TEMP_DOWNLOAD_PATH, exist_ok=True)

class ProcessTimeoutError(Exception):
    pass

@contextmanager
def process_timeout(seconds):
    def signal_handler(signum, frame):
        raise ProcessTimeoutError("Proceso tomó demasiado tiempo")
    
    # Establecer el manejador de señal
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Desactivar la alarma
        signal.alarm(0)

def kill_process_tree(process):
    try:
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass

def run_subprocess_with_timeout(command, timeout=300):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        raise
    finally:
        if process.poll() is None:
            kill_process_tree(process)

def get_video_info(video_url):
    try:
        command = [
            'yt-dlp',
            '--dump-json',
            video_url
        ]
        stdout, _ = run_subprocess_with_timeout(command, timeout=60)
        return json.loads(stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return f"Error obteniendo información del video: {str(e)}"
    except Exception as e:
        return str(e)

def download_video(video_url, quality):
    try:
        # Obtener información del video
        info = get_video_info(video_url)
        if isinstance(info, str):  # Si es un error
            return info
            
        # Preparar el nombre del archivo
        safe_title = re.sub(r'[<>:"/\\|?*]', '', info['title'])
        output_template = f'{TEMP_DOWNLOAD_PATH}/{safe_title}.%(ext)s'
        
        # Preparar el comando de descarga
        command = [
            'yt-dlp',
            '-f', quality,
            '--merge-output-format', 'mp4',
            '-o', output_template,
            video_url
        ]
        
        # Ejecutar el comando con timeout
        stdout, stderr = run_subprocess_with_timeout(command, timeout=600)
        
        # Encontrar el archivo descargado
        expected_file = f'{TEMP_DOWNLOAD_PATH}/{safe_title}.mp4'
        if os.path.isfile(expected_file):
            return expected_file
        else:
            return f"No se encontró el archivo descargado. Stdout: {stdout}, Stderr: {stderr}"
            
    except subprocess.TimeoutExpired:
        return "La descarga tomó demasiado tiempo y fue cancelada"
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
                return
        except PermissionError:
            print(f"Error de permiso al intentar eliminar el archivo: {file_path}. Reintentando en {retry_delay} segundos...")
            time.sleep(retry_delay)
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
    app.run(host="0.0.0.0", port=5011, debug=True)