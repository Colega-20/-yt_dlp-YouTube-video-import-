import yt_dlp
import os
from pathlib import Path

# Ruta de descarga personalizada (directorio local)
DOWNLOAD_PATH = "./descargas"  # Crea una carpeta 'descargas' en el mismo directorio del script

# Crear el directorio si no existe
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# Configuración de yt_dlp
ydl_opts = {
    'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',  # Ruta de descarga con formato de nombre
}

def dwl_vid(video_url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except yt_dlp.utils.DownloadError as e:
        print(f"Error al descargar el video: {e}")

def manage_downloads(path, max_files=4):
    # Listar archivos en la carpeta de descargas
    files = sorted(Path(path).iterdir(), key=os.path.getctime)
    
    # Si hay más de 'max_files', eliminar los más antiguos
    while len(files) > max_files:
        oldest_file = files.pop(0)
        print(f"Eliminando archivo antiguo: {oldest_file}")
        os.remove(oldest_file)

# Bucle principal
channel = 1
while channel == 1:
    link_of_the_video = input("Copia y pega la URL del video de YouTube: ").strip()
    
    # Validar que la URL sea correcta
    if not (link_of_the_video.startswith("http://") or link_of_the_video.startswith("https://")):
        print("La URL no es válida. Por favor, introduce una URL que comience con 'http://' o 'https://'.")
        continue
    
    # Descargar el video
    dwl_vid(link_of_the_video)
    
    # Gestionar archivos en la carpeta de descargas
    manage_downloads(DOWNLOAD_PATH, max_files=4)
    
    # Preguntar si desea continuar
    try:
        channel = int(input("Introduce 1 para descargar más videos o 0 para salir: "))
    except ValueError:
        print("Entrada inválida. Cerrando el programa.")
        break
