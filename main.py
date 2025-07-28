import os
import random
import asyncio
import datetime
import pickle
import subprocess
import threading
import schedule
import time
from flask import Flask
import edge_tts
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# === Ayarlar ===
BG_FOLDER = "backrounds"
MUSIC_FOLDER = "music"
QUOTES_FILE = "jp_quotes.txt"
UPLOADED_VIDEOS_FILE = "uploaded_videos.txt"

video_category_id = "22"  # People & Blogs
privacy_status = "public"
made_for_kids = False

video_tags = ["モチベーション", "日本語", "Shorts", "毎日", "インスピレーション"]

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Flask web server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot çalışıyor! 🟢"

def run_server():
    app.run(host="0.0.0.0", port=3000)

# YouTube API Authentication
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

def create_video(quote, timestamp):
    audio_path = f"voice_{timestamp}.mp3"
    video_path = f"video_{timestamp}.mp4"

    # Ses oluştur
    asyncio.run(generate_voice(quote, audio_path))

    # Arka plan resmi seç
    valid_image_exts = [".jpg", ".jpeg", ".png"]
    bg_images = [f for f in os.listdir(BG_FOLDER) if os.path.splitext(f)[1].lower() in valid_image_exts]
    bg_image_path = os.path.join(BG_FOLDER, random.choice(bg_images))

    # Müzik seç
    music_files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith(".mp3")]
    music_path = os.path.join(MUSIC_FOLDER, random.choice(music_files))

    # Arka plan videosu oluştur (8 sn)
    cmd_create_video = [
        "ffmpeg",
        "-loop", "1",
        "-i", bg_image_path,
        "-c:v", "libx264",
        "-t", "8",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        "-y",
        "temp_video.mp4"
    ]
    subprocess.run(cmd_create_video, check=True)

    # Süreler
    music_duration = get_audio_duration(music_path)
    voice_duration = get_audio_duration(audio_path)

    # Videoyu ses uzunluğuna göre kırp
    cmd_trim_video = [
        "ffmpeg",
        "-i", "temp_video.mp4",
        "-t", str(voice_duration),
        "-c", "copy",
        "-y",
        "trimmed_video.mp4"
    ]
    subprocess.run(cmd_trim_video, check=True)

    # Müziği ses uzunluğuna göre rastgele yerden başlat
    max_start = max(0, music_duration - voice_duration)
    start_time = random.uniform(0, max_start)

    merged_audio_path = f"merged_audio_{timestamp}.mp3"
    cmd_merge_audio_tracks = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", music_path,
        "-i", audio_path,
        "-filter_complex", "[1:a]volume=1[a0];[0:a]volume=0.3[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2",
        "-c:a", "mp3",
        "-y",
        merged_audio_path
    ]
    subprocess.run(cmd_merge_audio_tracks, check=True)

    # Son videoya ses ekle
    cmd_merge_audio = [
        "ffmpeg",
        "-i", "trimmed_video.mp4",
        "-i", merged_audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        "-y",
        video_path
    ]
    subprocess.run(cmd_merge_audio, check=True)

    # Geçici dosyalar temizle
    for temp_file in ["temp_video.mp4", "trimmed_video.mp4", audio_path, merged_audio_path]:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return video_path

def load_uploaded_videos():
    if not os.path.exists(UPLOADED_VIDEOS_FILE):
        open(UPLOADED_VIDEOS_FILE, "w").close()
        return set()
    with open(UPLOADED_VIDEOS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_uploaded_video(video_id):
    with open(UPLOADED_VIDEOS_FILE, "a") as f:
        f.write(video_id + "\n")

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

def job():
    print("✨ Video botu çalışıyor:", datetime.datetime.now())
    uploaded_videos = load_uploaded_videos()

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
        video_id = upload_video(
            youtube,
            video_file,
            video_title,
            video_description,
            video_tags,
            video_category_id,
            privacy_status,
            made_for_kids,
        )
        if video_id in uploaded_videos:
            print("⚠️ Bu video daha önce yüklenmiş, tekrar yüklenmiyor.")
        else:
            save_uploaded_video(video_id)
    except Exception as e:
        print("❌ Video yüklenirken hata:", e)

# Schedule (UTC)
schedule.every().day.at("22:30").do(job)  # 7:30 JST
schedule.every().day.at("09:00").do(job)  # 18:00 JST
schedule.every().day.at("12:30").do(job)  # 21:30 JST

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    print("🚀 Bot başladı, zamanlanmış görevler aktif.")
    while True:
        schedule.run_pending()
        time.sleep(60)
