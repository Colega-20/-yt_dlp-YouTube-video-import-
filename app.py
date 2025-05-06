from flask import Flask, request, render_template, send_from_directory, jsonify, send_file
import yt_dlp
import os
import threading
import time
import re
import urllib.parse
import mutagen
import requests
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, error
cookies_file='cookies.txt'
# Configurar logging para depuración
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuración de la API de YouTube
API_KEY = "AIzaSyAF0pP0QpfosKStRk_lQX3zoTNHHbmqF2A"  # Reemplaza con tu clave de API de YouTube
youtube = build('youtube', 'v3', developerKey=API_KEY)

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

def extract_video_id(url):
    """Extraer el ID del video de YouTube de una URL"""
    # Patrones comunes de URL de YouTube
    patterns = [
        r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_video_info(video_id):
    """Obtener información del video usando la API de YouTube"""
    try:
        # Solicitar detalles del video
        video_response = youtube.videos().list(
            part='snippet,contentDetails',
            id=video_id
        ).execute()
        
        if not video_response['items']:
            return None
        
        video_data = video_response['items'][0]
        
        # Obtener título, descripción y miniaturas
        title = video_data['snippet']['title']
        description = video_data['snippet']['description']
        thumbnails = video_data['snippet']['thumbnails']
        channel_title = video_data['snippet']['channelTitle']
        
        # Devolver la información recopilada
        return {
            'id': video_id,
            'title': title,
            'description': description,
            'thumbnails': thumbnails,
            'channel_title': channel_title
        }
        
    except HttpError as e:
        logger.error(f"Error en la API de YouTube: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return None

def clean_filename(filename):
    # Reemplazar caracteres especiales no deseados por espacios, pero mantener espacios normales
    filename = re.sub(r'[#&+:;,/\\*?<>|"]', ' ', filename)  
    # Eliminar espacios repetidos y recortar
    return re.sub(r'\s+', ' ', filename).strip()

def download_video(video_url, quality):
    try:
        # Extraer el ID del video
        video_id = extract_video_id(video_url)
        if not video_id:
            return {"error": "No se pudo extraer el ID del video de YouTube"}
        
        # Obtener información del video con la API de YouTube
        video_info = get_video_info(video_id)
        if not video_info:
            return {"error": "No se pudo obtener información del video"}
        
        # Verificar si la opción seleccionada es para extraer solo audio
        audio_only = "--extract-audio" in quality
        
        # Limpiar el título del video para usarlo como nombre de archivo
        safe_title = clean_filename(video_info['title'])
        
        # Configurar opciones base para todos los tipos de descargas
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{safe_title}.%(ext)s',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'},
            'no_check_certificate': True,
            'cookiefile': cookies_file,  # Agregar soporte para cookies
            'noplaylist': True,  # Don't download playlists
            'quiet': False,
            'verbose': True,     # Aumentar la verbosidad para depuración
        }
        
        # Configurar opciones específicas según el tipo de descarga
        if audio_only:
            # Para descarga de solo audio
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
                }],
            })
            expected_ext = '.mp3'
        else:
            # Para descarga de video
            ydl_opts.update({
                'format': quality,
                'merge_output_format': 'mp4',
                'noplaylist': True,  # Don't download playlists                
            })
            expected_ext = '.mp4'

        # Registrar la configuración para depuración
        # logger.debug(f"Opciones de descarga: {ydl_opts}")
        # logger.debug(f"URL de descarga: https://www.youtube.com/watch?v={video_id}")
        
        # Realizar la descarga
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            if error_code != 0:
                return {"error": f"yt-dlp devolvió código de error: {error_code}"}
        
        # Buscar el archivo descargado
        expected_filename = f"{safe_title}{expected_ext}"
        file_path = os.path.join(DOWNLOAD_FOLDER, expected_filename)
        
        # Si el archivo esperado no existe, buscar en la carpeta de descargas
        if not os.path.exists(file_path):
            logger.debug(f"Archivo esperado {file_path} no encontrado, buscando alternativas...")
      
        # Si es un archivo de audio, insertar metadatos y miniatura
        if file_path.endswith('.mp3') and video_info:
            try:
                from mutagen.id3 import ID3, TIT2, TPE1, APIC, error
                from PIL import Image
                from io import BytesIO

                audio = ID3(file_path)

                # Título y artista
                audio.add(TIT2(encoding=3, text=video_info['title']))
                audio.add(TPE1(encoding=3, text=video_info['channel_title']))

                # Descargar la miniatura disponible
                thumbnail_url = video_info['thumbnails'].get('default')['url']
                response = requests.get(thumbnail_url)
                if response.status_code == 200:
                    img_data = response.content
                    audio.add(APIC(
                        encoding=3,         # 3 = UTF-8
                        mime='image/Webp',  # o image/png
                        type=3,             # 3 = portada
                        desc='Cover',
                        data=img_data
                    ))

                audio.save()
                logger.info("Metadatos y miniatura agregados exitosamente.")
            except Exception as e:
                logger.warning(f"No se pudieron agregar metadatos o miniatura: {e}")

            # Buscar archivos con el título similar
            for file in os.listdir(DOWNLOAD_FOLDER):
                file_lower = file.lower()
                if file_lower.endswith(expected_ext.lower()):
                    # Verificar si el archivo contiene partes del título
                    if safe_title.lower() in file_lower:
                        file_path = os.path.join(DOWNLOAD_FOLDER, file)
                        logger.debug(f"Archivo encontrado: {file_path}")
                        break
        
        # Verificar que el archivo exista
        if not os.path.exists(file_path):
            logger.error(f"No se pudo encontrar el archivo descargado en {DOWNLOAD_FOLDER}")
            # Listar archivos en el directorio para depuración
            logger.debug(f"Contenido del directorio: {os.listdir(DOWNLOAD_FOLDER)}")
            return {"error": "No se pudo encontrar el archivo descargado"}
        
        # Registrar el archivo encontrado
        logger.info(f"Archivo descargado: {file_path}")
        
        # Registrar el acceso al archivo
        with lock:
            last_access_times[file_path] = time.time()

        return file_path
        
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error de descarga: {str(e)}")
        return {"error": f"Error de descarga: {str(e)}"}
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"No se pudo extraer la información del video: {str(e)}")
        return {"error": f"No se pudo extraer la información del video: {str(e)}"}
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        return {"error": f"Error inesperado: {str(e)}"}

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/video_info', methods=['GET'])
def get_video_info_api():
    """Endpoint para obtener información del video sin descargarlo"""
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "No se proporcionó una URL"}), 400
    
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "No se pudo extraer el ID del video"}), 400
    
    video_info = get_video_info(video_id)
    if not video_info:
        return jsonify({"error": "No se pudo obtener información del video"}), 500
    
    return jsonify(video_info)

@app.route('/download_video', methods=['POST'])
def download_video_route():
    try:
        video_url = request.form.get('video_url')
        quality = request.form.get('quality', 'best')

        if not video_url:
            return jsonify({"error": "No se proporcionó una URL"}), 400

        # Registrar solicitud para depuración
        logger.info(f"Solicitud de descarga: URL={video_url}, Calidad={quality}")
        
        # Verificar si es una descarga de solo audio
        audio_only = "--extract-audio" in quality
        logger.debug(f"¿Descarga de solo audio? {audio_only}")
        
        # Descargar el video o audio
        file_path = download_video(video_url, quality)
        
        # Verificar si hay un mensaje de error
        if isinstance(file_path, dict) and "error" in file_path:
            logger.error(f"Error en download_video: {file_path['error']}")
            return jsonify(file_path), 500
        
        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return jsonify({"error": f"Error al descargar: archivo no encontrado"}), 500
        
        # Esperar hasta que el archivo realmente exista y tenga contenido
        max_wait_time = 60  # Segundos máximo de espera
        start_time = time.time()

        while not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
            time.sleep(1)
            
            if time.time() - start_time > max_wait_time:
                logger.error("Timeout esperando a que el archivo esté completo")
                return jsonify({"error": "La descarga tardó demasiado en completarse"}), 500

        # Validar si el archivo se generó correctamente
        if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
            filename = os.path.basename(file_path)
            clean_name = clean_filename(filename)  # Aplicar limpieza
            
            # Determinar la extensión correcta según el tipo de descarga
            expected_ext = '.mp3' if audio_only else '.mp4'
            
            # Asegurarse de que el nombre del archivo tenga la extensión correcta
            if not clean_name.lower().endswith(expected_ext):
                clean_name += expected_ext
                
            # Crear la ruta completa para el archivo renombrado
            new_file_path = os.path.join(os.path.dirname(file_path), clean_name)
            
            # Evitar sobreescritura si ya existe un archivo con el mismo nombre
            if os.path.exists(new_file_path) and new_file_path != file_path:
                import random
                base_name = os.path.splitext(clean_name)[0]
                clean_name = f"{base_name}_{random.randint(1000, 9999)}{expected_ext}"
                new_file_path = os.path.join(os.path.dirname(file_path), clean_name)
                
            # Renombrar el archivo si es necesario
            if file_path != new_file_path:
                logger.debug(f"Renombrando archivo de {file_path} a {new_file_path}")
                os.rename(file_path, new_file_path)
                
            # URL segura para usar en el navegador
            safe_filename = urllib.parse.quote(clean_name)
            file_url = f"/statica/{safe_filename}"
            
            # Registrar el acceso al archivo
            with lock:
                last_access_times[new_file_path] = time.time()
                
            logger.info(f"Descarga completada: {new_file_path}")
            return jsonify({"downloadUrl": file_url})
        else:
            logger.error(f"Archivo inválido: {file_path}")
            return jsonify({"error": "El archivo descargado no es válido"}), 500
            
    except Exception as e:
        logger.error(f"Error inesperado en download_video_route: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error del servidor: {str(e)}"}), 500

# Nueva ruta para servir archivos descargados
@app.route('/statica/<path:filename>', methods=['GET'])
def serve_file(filename):
    try:
        # Decodificar el nombre del archivo para manejar caracteres especiales en la URL
        decoded_filename = urllib.parse.unquote(filename)
        
        # Actualizar el tiempo de último acceso
        full_path = os.path.join(app.config['DOWNLOAD_FOLDER'], decoded_filename)
        if os.path.exists(full_path):
            with lock:
                last_access_times[full_path] = time.time()
        else:
            logger.warning(f"Archivo solicitado no encontrado: {full_path}")
            return "Archivo no encontrado", 404
        
        # Registrar la solicitud de descarga
        logger.info(f"Enviando archivo: {full_path}")
        
        # Determinar el tipo MIME basado en la extensión del archivo
        mime_type = None
        if filename.lower().endswith('.mp3'):
            mime_type = 'audio/mpeg'
        elif filename.lower().endswith('.mp4'):
            mime_type = 'video/mp4'
        
        return send_from_directory(
            app.config['DOWNLOAD_FOLDER'], 
            decoded_filename, 
            as_attachment=True, 
            conditional=True,
            mimetype=mime_type
        )
    except Exception as e:
        logger.error(f"Error al servir archivo {filename}: {str(e)}", exc_info=True)
        return f"Error al servir el archivo: {str(e)}", 500

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
                        logger.info(f"Archivo eliminado por inactividad: {file}")
                        del last_access_times[file]
                except Exception as e:
                    logger.error(f"Error al eliminar {file}: {e}")

# Iniciar el hilo de limpieza en segundo plano
cleanup_thread = threading.Thread(target=cleanup_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5011, debug=True)
    input("Presiona Enter para salir...")