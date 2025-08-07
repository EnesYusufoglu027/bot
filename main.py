import os
import random
import asyncio
import datetime
import pickle
import subprocess

import edge_tts
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# === Ayarlar ===
BG_FOLDER = "backgrounds"
MUSIC_FOLDER = "music"
QUOTES_FILE = "jp_quotes.txt"
UPLOADED_VIDEOS_FILE = "uploaded_videos.txt"

video_category_id = "22"  # People & Blogs
privacy_status = "public"
made_for_kids = False

video_tags = ["モチベーション", "日本語", "Shorts", "毎日", "インスピレーション"]

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# === YouTube API Auth ===
def authenticate_youtube():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    youtube = build("youtube", "v3", credentials=creds)
    return youtube

# === Ses üretimi ===
async def generate_voice(text, audio_path):
    communicate = edge_tts.Communicate(text, voice="ja-JP-NanamiNeural")
    await communicate.save(audio_path)

def get_audio_duration(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path
    ]
    return float(subprocess.check_output(cmd).decode().strip())

# === Video oluşturma ===
def create_video(quote, timestamp):
    audio_path = f"voice_{timestamp}.mp3"
    video_path = f"video_{timestamp}.mp4"

    # Ses dosyasını oluştur
    asyncio.run(generate_voice(quote, audio_path))

    # Arka plan resmi seç
    valid_image_exts = [".jpg", ".jpeg", ".png"]
    bg_images = [f for f in os.listdir(BG_FOLDER) if os.path.splitext(f)[1].lower() in valid_image_exts]
    bg_image_path = os.path.join(BG_FOLDER, random.choice(bg_images))

    # Müzik seç
    music_files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith(".mp3")]
    music_path = os.path.join(MUSIC_FOLDER, random.choice(music_files))

    # Ses süreleri
    music_duration = get_audio_duration(music_path)
    voice_duration = get_audio_duration(audio_path)
    final_duration = max(10, voice_duration)  # En az 10 saniye

    # Müziği rastgele yerden başlat
    max_start = max(0, music_duration - final_duration)
    start_time = random.uniform(0, max_start)

    merged_audio_path = f"merged_audio_{timestamp}.mp3"
    subprocess.run([
        "ffmpeg",
        "-ss", str(start_time),
        "-i", music_path,
        "-i", audio_path,
        "-filter_complex",
        "[1:a]volume=1[a0];[0:a]volume=0.3[a1];[a0][a1]amix=inputs=2:duration=first",
        "-c:a", "mp3",
        "-y",
        merged_audio_path
    ], check=True)

    # Videoya yazı ekle + fade-in animasyon
    text_filter = (
        f"drawtext=text='{quote}':"
        "fontcolor=white:"
        "fontsize=48:"
        "box=1:boxcolor=black@0.5:boxborderw=10:"
        "x=(w-text_w)/2:"
        "y=(h-text_h)/2:"
        "enable='between(t,0,10)',"
        "fade=t=in:st=0:d=1"
    )

    subprocess.run([
        "ffmpeg",
        "-loop", "1",
        "-i", bg_image_path,
        "-i", merged_audio_path,
        "-t", str(final_duration),
        "-vf", f"scale=1080:1920,{text_filter}",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-y",
        video_path
    ], check=True)

    # Geçici dosyaları temizle
    for temp_file in [audio_path, merged_audio_path]:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return video_path


# === Video yükleme ===
def upload_video(youtube, video_file, title, description, tags, category_id, privacy, kids_flag):
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy,
            "madeForKids": kids_flag
        }
    }

    media = MediaFileUpload(video_file)
    response = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    ).execute()

    print(f"✅ Yüklendi: https://youtube.com/watch?v={response['id']}")
    return response["id"]

# === Ana görev ===
def job():
    print("✨ Video botu çalışıyor:", datetime.datetime.now())

    with open(QUOTES_FILE, "r", encoding="utf-8") as f:
        quotes = [line.strip() for line in f if line.strip()]
    quote = random.choice(quotes)

    video_title = f"{quote} - 毎日のモチベーション #Shorts"
    video_description = (
        "毎日の日本語モチベーションメッセージです。\n"
        "今日も素敵な一日をお過ごしください！\n"
        "チャンネル登録よろしくお願いします。\n"
        "#Shorts #モチベーション #日本語"
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    video_file = create_video(quote, timestamp)

    try:
        youtube = authenticate_youtube()
        upload_video(
            youtube,
            video_file,
            video_title,
            video_description,
            video_tags,
            video_category_id,
            privacy_status,
            made_for_kids,
        )
    except Exception as e:
        print("❌ Video yüklenirken hata:", e)

# === Ana başlatıcı ===
if __name__ == "__main__":
    job()

import os
import random
import datetime
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from flask import Flask
import threading

# 🔧 Ayarlar
QUOTE_FILE = "jp_quotes.txt"
OUTPUT_VIDEO = "output.mp4"
AUDIO_FILE = "voice.mp3"
BACKGROUND_FOLDER = "backgrounds"
FONT_PATH = "NotoSansJP-Regular.otf"
TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"

# YouTube API Ayarları
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CATEGORY_ID = "22"  # People & Blogs
TAGS = ["motivasyon", "Japonca", "hayat", "sabır", "umut", "özlü sözler"]

def load_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise Exception("❌ token.json bulunamadı. Yetkilendirme gerekli.")

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        raise Exception("❌ Token geçersiz. Tekrar yetkilendirme gerekiyor.")
    return creds

def generate_video():
    with open(QUOTE_FILE, "r", encoding="utf-8") as f:
        quotes = f.readlines()

    quote = random.choice(quotes).strip()
    bg_img = random.choice(os.listdir(BACKGROUND_FOLDER))
    bg_path = os.path.join(BACKGROUND_FOLDER, bg_img)

    background = ImageClip(bg_path).set_duration(10).resize(height=1920).crop(width=1080).set_fps(30)

    txt_clip = TextClip(
        quote,
        fontsize=80,
        font=FONT_PATH,
        color='white',
        size=(1000, None),
        method='caption'
    ).set_position("center").set_duration(10)

    final = CompositeVideoClip([background, txt_clip])
    final.write_videofile(OUTPUT_VIDEO, fps=30, audio=AUDIO_FILE)

def upload_to_youtube():
    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    title = f"Japonca Motivasyon | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    description = (
        "Her gün bir Japonca motivasyon sözü. Hayatınıza ilham katın!\n\n"
        "#motivasyon #japonca #özlüsözler\n"
        "🔔 Daha fazla video için abone olmayı unutmayın!"
    )

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": TAGS,
            "categoryId": CATEGORY_ID
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(OUTPUT_VIDEO)
    try:
        video = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        ).execute()
        print(f"✅ Video yüklendi: https://youtu.be/{video['id']}")
    except Exception as e:
        print(f"❌ Video yüklenirken hata: {e}")

def run_bot():
    print(f"✨ Video botu çalışıyor: {datetime.datetime.now()}")
    try:
        generate_video()
        upload_to_youtube()
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")

# Flask sunucusu (GitHub Actions yerine manuel test için)
app = Flask(__name__)

@app.route("/")
def index():
    threading.Thread(target=run_bot).start()
    return "⏳ Video oluşturuluyor ve yükleniyor..."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)


