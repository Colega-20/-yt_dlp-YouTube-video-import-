from flask import Flask, request, render_template, send_from_directory, jsonify, send_file
import yt_dlp
import os
import threading
import time
import re
import urllib.parse
import mutagen
import glob

app = Flask(__name__)

# Carpeta donde se guardarán los videos descargados
DOWNLOAD_FOLDER = "./descargas"
# Carpeta para almacenar archivos cookies.txt
COOKIES_FOLDER = "./cookies"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(COOKIES_FOLDER, exist_ok=True)
# Configurar Flask para servir archivos estáticos desde la carpeta de descargas
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['COOKIES_FOLDER'] = COOKIES_FOLDER
# Diccionario para rastrear el último acceso a cada archivo
last_access_times = {}
# Tiempo de inactividad para eliminar archivos (en segundos)
DELETE_AFTER = 300  # 5 minutos
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36' #user agent
# Bloqueo para evitar problemas de concurrencia
lock = threading.Lock()

# Ruta al archivo de cookies
COOKIES_FILE = os.path.join(COOKIES_FOLDER, "cookies.txt")

# Mapeo de números a opciones de calidad
QUALITY_OPTIONS = {
    '1': "bestaudio[ext=m4a]/best --extract-audio --audio-format mp3 --audio-quality 320K",  # Solo Audio (320kbps)
    '2': "bestvideo[height<=360][vcodec^=avc1]+bestaudio[ext=mp4]/best[vcodec^=avc1]",      # (360p)
    '3': "bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=mp4]/best[vcodec^=avc1]",      # SD (480p)
    '4': "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=mp4]/best[vcodec^=avc1]",      # HD (720p)
    '5': "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=mp4]/best[vcodec^=avc1]",     # Full HD (1080p)
    '6': "bestvideo[vcodec^=avc1]+bestaudio[ext=mp4]/best[vcodec^=avc1]"                    # Mejor calidad
}

def download_video(video_url, quality_option):
    try:
        # Convertir la opción numérica en el formato de calidad correspondiente
        quality = QUALITY_OPTIONS.get(quality_option, QUALITY_OPTIONS['4'])  # Por defecto HD (720p) si no existe la opción
        
        # Verificar si la opción seleccionada es para extraer solo audio
        audio_only = False
        audio_opts = {}
        
        if "--extract-audio" in quality:
            audio_only = True
            # Separar los parámetros de calidad de los parámetros de extracción de audio
            quality_parts = quality.split(" --extract-audio")
            base_format = quality_parts[0]
            
            # Configurar opciones para extraer solo audio con metadatos y thumbnail
            audio_opts = {
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '320K',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'writethumbnail': True,  # Descargar la miniatura
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    },
                    {
                       'key': 'FFmpegThumbnailsConvertor',  # Convertir miniatura a un formato más compatible
                       'format': 'WebP',
                    },
                    {
                        'key': 'EmbedThumbnail',  # Incrusta la miniatura en el archivo MP3
                    },
                    {
                        'key': 'FFmpegMetadata',  # Mantener los metadatos
                        'add_metadata': True,
                    }
                ],
                'format': base_format,
            }
        
        # Configuración base para todos los tipos de descargas
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'format': quality if not audio_only else None,
            'merge_output_format': 'mp4' if not audio_only else None,
            'user_agent': user_agent,
            'http_headers': {'User-Agent': user_agent},
            'noplaylist': True,  # Don't download playlists
        }
        
        # Verificar si existe un archivo de cookies.txt y añadirlo a las opciones
        if os.path.exists(COOKIES_FILE):
            # Añadir el archivo de cookies a las opciones, pero sin sobrescribir la configuración de formato
            ydl_opts['cookiefile'] = COOKIES_FILE
            print(f"Usando archivo de cookies: {COOKIES_FILE}")
        
        # Si es solo audio, actualizar las opciones
        if audio_only:
            ydl_opts.update(audio_opts)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_path = ydl.prepare_filename(info)
            
            # Determinar la extensión correcta basada en si es solo audio o video
            if audio_only:
                base_path = os.path.splitext(file_path)[0]
                file_path = f"{base_path}.mp3"
            else:
                base_path = os.path.splitext(file_path)[0]
                file_path = f"{base_path}.mp4"
                
            # Registrar el acceso al archivo
            with lock:
                last_access_times[file_path] = time.time()

            return file_path
        
    except yt_dlp.utils.DownloadError as e:
        return {"error": f"Download error: {str(e)}"}
    except yt_dlp.utils.ExtractorError as e:
        return {"error": f"Could not extract video information: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    
def clean_filename(filename):
    # Eliminar emojis
    # filename = emoji.replace_emoji(filename, replace=" ")  
    # Reemplazar caracteres especiales no deseados por espacios, pero mantener espacios normales
    filename = re.sub(r'[#&+:;,/\\*?<>|"]', ' ', filename)  
    # Eliminar espacios repetidos y recortar
    return re.sub(r'\s+', ' ', filename).strip()


@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/upload_cookies', methods=['POST'])
def upload_cookies():
    if 'cookies_file' not in request.files:
        return jsonify({"error": "No se subió ningún archivo de cookies"}), 400
    
    cookies_file = request.files['cookies_file']
    
    if cookies_file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
    
    # Guardar el archivo de cookies en el directorio de cookies
    try:
        cookies_path = os.path.join(app.config['COOKIES_FOLDER'], "cookies.txt")
        cookies_file.save(cookies_path)
        
        # Verificar que el archivo se guardó correctamente
        if not os.path.exists(cookies_path):
            return jsonify({"error": "Error al guardar el archivo de cookies"}), 500
            
        return jsonify({"success": True, "message": "Archivo de cookies subido correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo de cookies: {str(e)}"}), 500

@app.route('/download_video', methods=['POST'])
def download_video_route():
    video_url = request.form.get('video_url')
    quality_option = request.form.get('quality', '4')  # Por defecto HD (720p) = 4

    if not video_url:
        return jsonify({"error": "No se proporcionó una URL"}), 400

    # Obtener el formato real de calidad a partir de la opción numérica
    quality = QUALITY_OPTIONS.get(quality_option, QUALITY_OPTIONS['4'])  # Por defecto HD (720p) si no existe
    
    # Verificar si es una descarga de solo audio
    audio_only = "--extract-audio" in quality
    
    # Descargar el video o audio en un hilo separado
    file_path = download_video(video_url, quality_option)
    
    # Verificar si hay un mensaje de error
    if isinstance(file_path, dict) and "error" in file_path:
        return jsonify(file_path), 500
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"Error al descargar: {file_path}"}), 500
    
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
        
        # Asegúrate de que el nombre del archivo termine con la extensión correcta
        expected_ext = '.mp3' if audio_only else '.mp4'
        if not clean_name.lower().endswith(expected_ext):
            clean_name += expected_ext
            
        # Renombrar el archivo con el nuevo nombre limpio
        new_file_path = os.path.join(os.path.dirname(file_path), clean_name)
        
        # Si el archivo ya existe, no sobrescribas (evita conflictos)
        if os.path.exists(new_file_path) and new_file_path != file_path:
            # Agrega un número aleatorio para hacerlo único
            import random
            base_name = os.path.splitext(clean_name)[0]
            clean_name = f"{base_name} {random.randint(1000, 9999)}{expected_ext}"
            new_file_path = os.path.join(os.path.dirname(file_path), clean_name)
            
        # Ahora sí, renombra el archivo
        if file_path != new_file_path:
            os.rename(file_path, new_file_path)
            
        # URL segura para usar en el navegador (codifica los espacios y caracteres especiales)
        safe_filename = urllib.parse.quote(clean_name)
        file_url = f"/statica/{safe_filename}"
        
        # Registrar el acceso al archivo
        with lock:
            last_access_times[new_file_path] = time.time()
            
        return jsonify({"downloadUrl": file_url})

    return jsonify({"error": f"Error al descargar: {file_path}"}), 500

# Nueva ruta para servir archivos descargados
@app.route('/statica/<path:filename>', methods=['GET'])
def serve_file(filename):
    # Decodificar el nombre del archivo para manejar caracteres especiales en la URL
    decoded_filename = urllib.parse.unquote(filename)
    
    # Actualizar el tiempo de último acceso
    full_path = os.path.join(app.config['DOWNLOAD_FOLDER'], decoded_filename)
    if os.path.exists(full_path):
        with lock:
            last_access_times[full_path] = time.time()
    
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], decoded_filename, as_attachment=True, conditional=True)


def cleanup_files():
    """Elimina archivos que han estado inactivos por más de DELETE_AFTER segundos"""
    while True:
        time.sleep(20)  # Verificar cada 20 segundos

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
    input("Presiona Enter para salir...")