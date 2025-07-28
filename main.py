def create_video(quote, timestamp):
    audio_path = f"voice_{timestamp}.mp3"
    video_path = f"video_{timestamp}.mp4"

    # Ses dosyası oluştur
    asyncio.run(generate_voice(quote, audio_path))

    # Arka plan resmi seç
    valid_image_exts = [".jpg", ".jpeg", ".png"]
    bg_images = [f for f in os.listdir(BG_FOLDER) if os.path.splitext(f)[1].lower() in valid_image_exts]
    bg_image_path = os.path.join(BG_FOLDER, random.choice(bg_images))

    # Müzik seç
    music_files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith(".mp3")]
    music_path = os.path.join(MUSIC_FOLDER, random.choice(music_files))

    # Ses uzunluğu
    voice_duration = get_audio_duration(audio_path)

    # -----------------------
    # Video oluşturma:  
    # 1) Resme zoom-in animasyonu ekle (zoom +0.001 her frame)  
    # 2) Metni ekranın ortasında, dikeyde kayan (scrolling) animasyonla göster  
    # 3) 1080x1920 (9:16) formatında  
    # -----------------------

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # GitHub Actions'ta yüklü
    duration = voice_duration

    # ffmpeg filter_complex için metin içinde özel karakterler kaçış yapıldı
    safe_quote = quote.replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")

    filter_complex = (
        f"[0:v]scale=1080:1920,zoompan=z='zoom+0.001':d={int(duration*30)},"
        f"fps=30,format=yuv420p[v];"
        f"color=c=black@0.0:size=1080x1920:d={int(duration*30)}[black];"
        f"[black][v]overlay=format=auto:shortest=1[bg];"
        f"[bg]drawtext=fontfile={font_path}:text='{safe_quote}':"
        f"fontcolor=white:fontsize=70:borderw=2:bordercolor=black@0.7:"
        f"x='(w-text_w)/2':"
        f"y='h-(mod(n*5\\,{int(duration*30*5)})*h/{int(duration*30)})'"
    )

    cmd_create_video = [
        "ffmpeg",
        "-loop", "1",
        "-i", bg_image_path,
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y",
        "temp_video.mp4"
    ]
    subprocess.run(cmd_create_video, check=True)

    # Müziği ve sesi birleştirme kısmı aynı kalabilir
    music_duration = get_audio_duration(music_path)

    # Videoyu sesi kadar kırp (zaten temp_video.mp4 süreli)
    cmd_trim_video = [
        "ffmpeg",
        "-i", "temp_video.mp4",
        "-t", str(duration),
        "-c", "copy",
        "-y",
        "trimmed_video.mp4"
    ]
    subprocess.run(cmd_trim_video, check=True)

    max_start = max(0, music_duration - duration)
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

    # Geçici dosyalar
    for temp_file in ["temp_video.mp4", "trimmed_video.mp4", audio_path, merged_audio_path]:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return video_path
