import os
import base64
import subprocess
import asyncio
from datetime import datetime
import edge_tts

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# === Kimlik dosyaları (token.json vs.) ===

token_b64 = os.environ.get("TOKEN_JSON_BASE64")
if token_b64:
    with open("token.json", "wb") as f:
        f.write(base64.b64decode(token_b64))
    print("✅ token.json oluşturuldu.")
else:
    print("⚠️ TOKEN_JSON_BASE64 bulunamadı, YouTube yükleme atlanacak.")

# === Video, Ses yolları ===

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
IMAGE_PATH = "backgrounds/pexels-taha-balta-3031128-5059201.jpg"
TEXT = "Karlı havalarda yavaş gidin ve takip mesafesini artırın."

AUDIO_PATH = f"voice_{TIMESTAMP}.mp3"
VIDEO_PATH = f"temp_video.mp4"
FINAL_VIDEO = f"video_{TIMESTAMP}.mp4"
OUTPUT_DIR = "output_videos"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# === Ses üretimi ===

async def generate_tts(text, out_path):
    print(f"🔊 Ses oluşturuluyor: {text}")
    communicate = edge_tts.Communicate(text, voice="tr-TR-EmelNeural")
    await communicate.save(out_path)
    print(f"✅ Ses dosyası kaydedildi: {out_path}")


# === Videoya yazı + ses gömme ===

def create_video_with_text(image_path, text, video_path):
    print(f"📷 Arka plan: {image_path}")
    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", f"scale=1080:1920,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{text}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2",
        "-t", "8",
        "-r", "25",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        video_path
    ]
    subprocess.run(command, check=True)
    print(f"✅ Video üretildi: {video_path}")


def merge_audio_with_video(video_input, audio_input, output_path):
    command = [
        "ffmpeg", "-y",
        "-i", video_input,
        "-i", audio_input,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    subprocess.run(command, check=True)
    print(f"✅ Ses gömülü video hazır: {output_path}")


# === YouTube’a yükleme (geçici devre dışı) ===

def upload_to_youtube(video_file, title, description):
    if not os.path.exists("token.json"):
        print("⚠️ token.json yok, YouTube yükleme atlanıyor.")
        return

    try:
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/youtube.upload"])
        youtube = build("youtube", "v3", credentials=creds)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": "27"
                },
                "status": {
                    "privacyStatus": "unlisted"
                }
            },
            media_body=MediaFileUpload(video_file)
        )
        response = request.execute()
        print(f"📤 Yüklendi: https://youtu.be/{response['id']}")
    except HttpError as e:
        print(f"❌ Yükleme hatası: {e}")


# === Ana fonksiyon ===

async def main():
    print(f"✨ Video oluşturuluyor: {datetime.now()}")

    await generate_tts(TEXT, AUDIO_PATH)
    create_video_with_text(IMAGE_PATH, TEXT, VIDEO_PATH)
    merge_audio_with_video(VIDEO_PATH, AUDIO_PATH, FINAL_VIDEO)

    # Kaydet
    final_path = os.path.join(OUTPUT_DIR, FINAL_VIDEO)
    os.rename(FINAL_VIDEO, final_path)
    print(f"💾 Video kaydedildi: {final_path}")

    # Şimdilik devre dışı:
    upload_to_youtube(final_path, "Trafik Uyarısı", "Edge-TTS ile oluşturuldu.")

if __name__ == "__main__":
    asyncio.run(main())
