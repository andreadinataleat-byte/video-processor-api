from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import ffmpeg
import os
import uuid

app = FastAPI(title="Video Processing API per n8n")

# Directory temporanea all'interno del container per salvare i file
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class DownloadRequest(BaseModel):
    url: str

class EditLogoRequest(BaseModel):
    video_path: str
    x: int
    y: int
    w: int
    h: int

class BurnSubtitlesRequest(BaseModel):
    video_path: str
    srt_content: str

class CropShortsRequest(BaseModel):
    video_path: str

class ReplaceAudioRequest(BaseModel):
    video_path: str
    new_audio_path: str
    original_volume: float = 0.15  # Abbassa il volume originale al 15%
    new_audio_volume: float = 1.0  # Mantiene il nuovo audio (es. doppiaggio IA) al 100%

@app.get("/")
def read_root():
    return {"status": "online", "message": "Video Processing API operativa"}

@app.post("/download-and-extract")
def download_and_extract(req: DownloadRequest):
    """
    Scarica uno YouTube Short tramite URL ed estrae la traccia audio in MP3.
    Restituisce i percorsi dei file scaricati.
    """
    video_id = str(uuid.uuid4())
    video_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    audio_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': video_path,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        # 1. Download Video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.url])
        
        # 2. Estrazione Audio con FFmpeg
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_path, format='mp3', acodec='libmp3lame', audio_bitrate='128k')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)

        return {
            "success": True,
            "video_path": video_path,
            "audio_path": audio_path,
            "message": "Video scaricato e audio estratto con successo."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'elaborazione: {str(e)}")

@app.post("/remove-logo")
def remove_logo(req: EditLogoRequest):
    """
    Applica una sfocatura (blur) su una zona specifica del video per nascondere watermark/loghi.
    Le coordinate x, y, w (larghezza), h (altezza) indicano il rettangolo da sfocare.
    """
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail="Video non trovato")
        
    output_path = req.video_path.replace(".mp4", "_nologo.mp4")
    
    try:
        stream = ffmpeg.input(req.video_path)
        # Il filtro delogo applica una sfocatura
        stream = ffmpeg.output(stream, output_path, vf=f"delogo=x={req.x}:y={req.y}:w={req.w}:h={req.h}")
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        return {
            "success": True, 
            "output_path": output_path,
            "message": "Watermark sfocato con successo."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'editing: {str(e)}")

@app.post("/burn-subtitles")
def burn_subtitles(req: BurnSubtitlesRequest):
    """
    Prende un file video e una stringa contenente i sottotitoli in formato SRT.
    Stampa i sottotitoli in sovrimpressione sul video.
    """
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail="Video non trovato")
        
    srt_path = req.video_path.replace(".mp4", ".srt")
    output_path = req.video_path.replace(".mp4", "_subbed.mp4")
    
    # Salva il contenuto SRT in un file fisico necessario a ffmpeg
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(req.srt_content)
        
    try:
        stream = ffmpeg.input(req.video_path)
        
        # Applica i sottotitoli con uno stile base (Giallo, Bordo Nero, Centrale) tipico da Shorts
        # MarginV alza i sottotitoli dal fondo per non coprire i comandi di TikTok/Shorts
        vf_string = f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFF,Outline=1,Shadow=1,MarginV=40,Alignment=2'"
        
        stream = ffmpeg.output(stream, output_path, vf=vf_string)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        return {
            "success": True, 
            "output_path": output_path,
            "message": "Sottotitoli applicati con successo."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'applicazione dei sottotitoli: {str(e)}")

@app.post("/auto-crop-shorts")
def auto_crop_shorts(req: CropShortsRequest):
    """
    [Funzione PRO]: Trasforma qualsiasi video orizzontale in un perfetto Shorts verticale (9:16)
    effettuando un ritaglio (crop) centrato, e normalizza l'audio per renderlo 'virale' e potente.
    """
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail="Video non trovato")
        
    output_path = req.video_path.replace(".mp4", "_cropped.mp4")
    
    try:
        # Crop centrato 9:16
        stream_video = ffmpeg.input(req.video_path).video.filter('crop', 'ih*(9/16)', 'ih')
        # Normalizzazione audio per YouTube Shorts (loudnorm)
        stream_audio = ffmpeg.input(req.video_path).audio.filter('loudnorm')
        
        stream = ffmpeg.output(stream_video, stream_audio, output_path)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        return {"success": True, "output_path": output_path, "message": "Video croppato e audio normalizzato."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il crop: {str(e)}")

@app.post("/replace-audio")
def replace_audio(req: ReplaceAudioRequest):
    """
    [Funzione PRO]: Se usi ElevenLabs o TTS per doppiare il video, questo endpoint unisce 
    il nuovo audio al video, abbassando il volume originale per mantenere in sottofondo gli effetti sonori.
    """
    if not os.path.exists(req.video_path) or not os.path.exists(req.new_audio_path):
        raise HTTPException(status_code=404, detail="File non trovati")
        
    output_path = req.video_path.replace(".mp4", "_dubbed.mp4")
    
    try:
        video_input = ffmpeg.input(req.video_path)
        new_audio_input = ffmpeg.input(req.new_audio_path)
        
        # Abbassa l'audio originale del video
        original_audio_lowered = video_input.audio.filter('volume', req.original_volume)
        # Regola il volume del nuovo audio
        new_audio_adjusted = new_audio_input.audio.filter('volume', req.new_audio_volume)
        
        # Mixa le due tracce audio
        mixed_audio = ffmpeg.filter([original_audio_lowered, new_audio_adjusted], 'amix', inputs=2, duration='first')
        
        # Unisce il video originale con l'audio mixato
        stream = ffmpeg.output(video_input.video, mixed_audio, output_path, acodec='aac')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        return {"success": True, "output_path": output_path, "message": "Audio sostituito e mixato con successo."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel mix audio: {str(e)}")
