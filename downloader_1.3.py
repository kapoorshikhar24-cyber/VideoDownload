#!/usr/bin/env python3
"""
Ultimate YouTube Video Downloader
A premium, feature-rich Python script that offers both:
1. A stunning, modern web GUI (HTML/CSS/JS glassmorphic design using Eel,
   separate threads to prevent freezing, progress bars, and quality options).
2. A beautiful, colored Command Line Interface (CLI) for power users.

Author: Antigravity AI
Version: 1.3.0
"""

import os
import sys
import time
import threading
import json
import urllib.request
import urllib.error
import subprocess
from datetime import timedelta

# Reconfigure standard streams to UTF-8 to prevent encoding crashes on Windows CLI
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Global variables for auto-installation tracking
DEPENDENCIES_CHECKED = False
YT_DLP_AVAILABLE = False
EEL_AVAILABLE = False
yt_dlp = None
eel = None
CANCEL_DOWNLOAD = False
PAUSE_DOWNLOAD = threading.Event()
PAUSE_DOWNLOAD.set()

def check_and_install_dependencies():
    """
    Checks if necessary third-party libraries (yt-dlp, eel) are installed.
    If not, attempts to install them automatically using pip.
    Reads requirements.txt if present.
    """
    global DEPENDENCIES_CHECKED, YT_DLP_AVAILABLE, EEL_AVAILABLE, yt_dlp, eel
    if DEPENDENCIES_CHECKED:
        return True

    # 1. Check requirements.txt
    script_dir = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(script_dir, "requirements.txt")
    if os.path.exists(req_file):
        print("[*] Found requirements.txt. Checking/installing dependencies...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("[+] Successfully installed/updated dependencies from requirements.txt!")
        except Exception as e:
            print(f"[-] Failed to install from requirements.txt: {e}. Trying fallback individual installation...")

    # 2. Check yt-dlp
    try:
        import yt_dlp as yt_dlp_module
        yt_dlp = yt_dlp_module
        YT_DLP_AVAILABLE = True
    except ImportError:
        print("[*] yt-dlp is not installed. Attempting to install it automatically...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            import yt_dlp as yt_dlp_module
            yt_dlp = yt_dlp_module
            YT_DLP_AVAILABLE = True
            print("[+] Successfully installed yt-dlp!")
        except Exception as e:
            print(f"[-] Failed to automatically install yt-dlp: {e}")

    # 3. Check eel
    try:
        import eel as eel_module
        eel = eel_module
        EEL_AVAILABLE = True
    except ImportError:
        print("[*] Eel is not installed. Attempting to install it automatically...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "eel"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            import eel as eel_module
            eel = eel_module
            EEL_AVAILABLE = True
            print("[+] Successfully installed Eel!")
        except Exception as e:
            print(f"[-] Failed to automatically install Eel: {e}")

    DEPENDENCIES_CHECKED = True
    return YT_DLP_AVAILABLE and EEL_AVAILABLE

# Initial check to load modules if already installed
try:
    import yt_dlp as yt_dlp_module
    yt_dlp = yt_dlp_module
    YT_DLP_AVAILABLE = True
except ImportError:
    pass

try:
    import eel as eel_module
    eel = eel_module
    EEL_AVAILABLE = True
except ImportError:
    pass


# Helper Functions
def format_bytes(bytes_num):
    """Formats bytes into human-readable strings (KB, MB, GB)."""
    if not bytes_num:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} TB"

def format_duration(seconds):
    """Formats seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "0:00"
    return str(timedelta(seconds=int(seconds))).lstrip("0:") or "0:00"

def get_default_download_dir():
    """Gets the user's default Downloads directory across operating systems."""
    if os.name == 'nt':
        import winreg
        try:
            sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                return winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
        except Exception:
            return os.path.join(os.path.expanduser('~'), 'Downloads')
    return os.path.join(os.path.expanduser('~'), 'Downloads')

def check_ffmpeg():
    """Checks if ffmpeg is available on the system path or in WinGet local packages."""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
        return True
    except Exception:
        pass

    # If not on standard path, check common installation paths on Windows (like WinGet)
    if os.name == 'nt':
        try:
            local_appdata = os.environ.get('LOCALAPPDATA')
            if local_appdata:
                winget_path = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Packages')
                if os.path.exists(winget_path):
                    for root, dirs, files in os.walk(winget_path):
                        if 'ffmpeg.exe' in files:
                            ffmpeg_bin = os.path.join(root, 'ffmpeg.exe')
                            # Verify the executable is functional
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = 0
                            subprocess.run([ffmpeg_bin, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
                            
                            # Add to current process path so yt-dlp can locate it
                            ffmpeg_dir = os.path.dirname(ffmpeg_bin)
                            if ffmpeg_dir not in os.environ['PATH']:
                                os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
                            return True
        except Exception:
            pass
    return False

FFMPEG_AVAILABLE = check_ffmpeg()

# History persistence functions
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_history.json")

def load_history():
    """Loads download history from the local JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_to_history(title, file_path, format_type, size):
    """Saves a download record to the local JSON file."""
    history = load_history()
    history.insert(0, {
        "title": title,
        "path": file_path,
        "format": format_type,
        "size": size,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    history = history[:100]  # Keep last 100 entries
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# ==============================================================================
# 1. COMMAND LINE INTERFACE (CLI) MODE
# ==============================================================================
class DownloaderCLI:
    def __init__(self, urls, output_dir=None, audio_only=False, quality='best'):
        self.urls = urls if isinstance(urls, list) else [urls]
        self.output_dir = output_dir or get_default_download_dir()
        self.audio_only = audio_only
        self.quality = quality
        self.last_progress_update = 0

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            percent = (downloaded / total) * 100 if total > 0 else 0
            
            current_time = time.time()
            if current_time - self.last_progress_update > 0.1 or percent >= 100:
                self.last_progress_update = current_time
                
                bar_length = 30
                filled_length = int(round(bar_length * percent / 100))
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                speed_str = f"{format_bytes(speed)}/s" if speed else "N/A"
                eta_str = f"{eta}s" if eta else "N/A"
                
                sys.stdout.write(
                    f"\r\033[94m[Downloading]\033[0m |{bar}| {percent:.1f}% "
                    f"({format_bytes(downloaded)}/{format_bytes(total)}) | "
                    f"Speed: \033[92m{speed_str}\033[0m | ETA: \033[93m{eta_str}\033[0m   "
                )
                sys.stdout.flush()
                
        elif d['status'] == 'finished':
            sys.stdout.write("\n\033[92m[+] Download finished! Post-processing...\033[0m\n")
            sys.stdout.flush()

    def run(self):
        print("\n" + "="*80)
        print(" \033[95mUltimate YouTube Downloader\033[0m - CLI Mode")
        print("="*80)
        
        if not YT_DLP_AVAILABLE:
            print("\033[91m[-] Error: yt-dlp is required. Please install it using 'pip install yt-dlp'.\033[0m")
            return False

        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'no_warnings': True,
            'concurrent_fragment_downloads': 10,
            'source_address': '0.0.0.0',
        }
        
        if self.audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best/b',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            if self.quality == 'best':
                ydl_opts.update({'format': 'bestvideo*+bestaudio/best/b'})
            else:
                ydl_opts.update({
                    'format': f'bestvideo[height<=?{self.quality}]+bestaudio/best[height<=?{self.quality}]/bestvideo*+bestaudio/best/b'
                })

        overall_success = True
        
        for idx, url in enumerate(self.urls, 1):
            if len(self.urls) > 1:
                print(f"\n\033[96m[Batch] Processing URL {idx} of {len(self.urls)}: {url}\033[0m")
                
            actual_url = url
            if not url.startswith("http://") and not url.startswith("https://"):
                print(f"[*] Searching YouTube for query: '{url}'...")
                actual_url = f"ytsearch1:{url}"

            print(f"[*] Extracting video info...")
            
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    info = ydl.extract_info(actual_url, download=False)
                
                # Handle search results
                if 'entries' in info and info.get('_type') == 'playlist' and actual_url.startswith("ytsearch"):
                    if not info['entries']:
                        print("\033[91m[-] No search results found.\033[0m")
                        overall_success = False
                        continue
                    # Grab the first match
                    entry = info['entries'][0]
                    actual_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    print(f"[+] Found search match: {entry.get('title')}")
                    # re-extract full metadata
                    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                        info = ydl.extract_info(actual_url, download=False)

                # Handle Playlists in CLI
                if info.get('_type') == 'playlist':
                    print(f"\033[92m[+] Playlist Found!\033[0m")
                    print(f"     - Title: {info.get('title', 'Unknown')}")
                    print(f"     - Videos: {len(info.get('entries', []))}")
                    print("--------------------------------------------------------------------------------")
                    
                    success_count = 0
                    for index, entry in enumerate(info['entries'], 1):
                        if not entry:
                            continue
                        video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        print(f"\n[*] Downloading Video {index} of {len(info['entries'])}: {entry.get('title')}")
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl_dl:
                                res_info = ydl_dl.extract_info(video_url, download=True)
                                final_path = res_info.get('_filename')
                                if 'requested_downloads' in res_info and res_info['requested_downloads']:
                                    final_path = res_info['requested_downloads'][0].get('filepath', final_path)
                                size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
                                save_to_history(
                                    res_info.get('title', entry.get('title')),
                                    final_path or "Unknown Location",
                                    'MP3 Audio' if self.audio_only else 'MP4 Video',
                                    format_bytes(size_val)
                                )
                                success_count += 1
                        except Exception as e:
                            print(f"\033[91m[-] Failed to download playlist item {index}: {e}\033[0m")
                    
                    print(f"\n\033[92m[+] Completed: Downloaded {success_count}/{len(info['entries'])} items.\033[0m\n")
                    if success_count == 0:
                        overall_success = False
                    continue

                # Single Video Download
                print(f"\033[92m[+] Video Found!\033[0m")
                print(f"     - Title: {info.get('title', 'Unknown')}")
                print(f"     - Channel: {info.get('uploader', 'Unknown')}")
                print(f"     - Duration: {format_duration(info.get('duration'))}")
                print(f"     - Output Directory: {self.output_dir}")
                print(f"     - Format: {'MP3 Audio' if self.audio_only else f'MP4 Video ({self.quality}p)'}")
                print("--------------------------------------------------------------------------------")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res_info = ydl.extract_info(actual_url, download=True)
                    final_path = res_info.get('_filename')
                    if 'requested_downloads' in res_info and res_info['requested_downloads']:
                        final_path = res_info['requested_downloads'][0].get('filepath', final_path)
                    size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
                    save_to_history(
                        res_info.get('title', 'Unknown'),
                        final_path or "Unknown Location",
                        'MP3 Audio' if self.audio_only else 'MP4 Video',
                        format_bytes(size_val)
                    )
                    
                print("\033[92m[+] Done with this item.\033[0m\n")
                
            except Exception as e:
                print(f"\n\033[91m[-] Error occurred processing '{url}': {e}\033[0m")
                print("\033[93m[!] Tip: If download fails with merge errors, you may need 'ffmpeg' installed on your system.\033[0m\n")
                overall_success = False

        if len(self.urls) > 1:
            print(f"\033[92m[+] Batch Processing Complete!\033[0m\n")
        return overall_success


# ==============================================================================
# 2. EEL WEB-BASED GUI BRIDGE EXPOSURE
# ==============================================================================
CANCEL_DOWNLOAD = False

def register_eel_exposures():
    """
    Registers Python functions to be available in the JavaScript context.
    """
    import eel

    @eel.expose
    def get_default_dir():
        return get_default_download_dir()

    @eel.expose
    def check_ffmpeg_status():
        return FFMPEG_AVAILABLE

    @eel.expose
    def get_history():
        return load_history()

    @eel.expose
    def clear_history():
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass
        return []

    @eel.expose
    def remove_history_item(index):
        history = load_history()
        if 0 <= index < len(history):
            history.pop(index)
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=4, ensure_ascii=False)
            except Exception:
                pass
        return history

    @eel.expose
    def play_file(file_path):
        if not os.path.exists(file_path):
            return "File does not exist or has been deleted/moved."
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
            return True
        except Exception as e:
            return str(e)

    @eel.expose
    def open_folder(file_path):
        if not os.path.exists(file_path):
            return "File folder does not exist."
        try:
            abs_path = os.path.normpath(file_path)
            if os.name == 'nt':
                subprocess.run(['explorer', '/select,', abs_path])
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', abs_path])
            else:
                dir_path = os.path.dirname(abs_path)
                subprocess.run(['xdg-open', dir_path])
            return True
        except Exception as e:
            return str(e)

    @eel.expose
    def get_clipboard_text():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            text = root.clipboard_get()
        except Exception:
            text = ""
        root.destroy()
        return text

    @eel.expose
    def browse_dir(current_dir):
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(initialdir=current_dir, parent=root)
        root.destroy()
        return folder

    @eel.expose
    def pause_download():
        global PAUSE_DOWNLOAD
        PAUSE_DOWNLOAD.clear()

    @eel.expose
    def resume_download():
        global PAUSE_DOWNLOAD
        PAUSE_DOWNLOAD.set()

    @eel.expose
    def cancel_download():
        global CANCEL_DOWNLOAD, PAUSE_DOWNLOAD
        CANCEL_DOWNLOAD = True
        PAUSE_DOWNLOAD.set()

    # Asynchronous Workers wrappers
    @eel.expose
    def analyze_url(url):
        threading.Thread(target=analyze_url_worker, args=(url,), daemon=True).start()

    @eel.expose
    def analyze_playlist(url):
        threading.Thread(target=analyze_playlist_worker, args=(url,), daemon=True).start()

    @eel.expose
    def search_youtube(query):
        threading.Thread(target=search_youtube_worker, args=(query,), daemon=True).start()

    @eel.expose
    def download_single(url, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles):
        threading.Thread(
            target=download_single_worker,
            args=(url, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles),
            daemon=True
        ).start()

    @eel.expose
    def download_playlist(entries, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles):
        threading.Thread(
            target=download_playlist_worker,
            args=(entries, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles),
            daemon=True
        ).start()


# Workers Implementations
def analyze_url_worker(url):
    import eel
    if not YT_DLP_AVAILABLE:
        eel.on_fetch_failed("yt-dlp package is missing.")()
        return
    
    actual_url = url
    if not url.startswith("http://") and not url.startswith("https://"):
        actual_url = f"ytsearch1:{url}"

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'source_address': '0.0.0.0',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(actual_url, download=False)
            
        if 'entries' in info and info.get('_type') == 'playlist' and actual_url.startswith("ytsearch"):
            if not info['entries']:
                eel.on_fetch_failed("No search results found.")()
                return
            entry = info['entries'][0]
            actual_url = f"https://www.youtube.com/watch?v={entry['id']}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                info = ydl2.extract_info(actual_url, download=False)
        
        meta = {
            'title': info.get('title', 'Unknown Title'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Unknown Channel'),
            'view_count': info.get('view_count', 0),
            'original_url': url,
            'webpage_url': info.get('webpage_url', url)
        }
        eel.on_fetch_success(meta)()
    except Exception as e:
        err_msg = str(e).split('\n')[0]
        eel.on_fetch_failed(err_msg)()

def analyze_playlist_worker(url):
    import eel
    if not YT_DLP_AVAILABLE:
        eel.on_playlist_fetch_failed("yt-dlp package is missing.")()
        return

    # Check for multiple URLs separated by commas or spaces
    raw_urls = url.replace(',', ' ').split()
    urls = [u.strip() for u in raw_urls if u.strip()]

    if len(urls) > 1:
        # Custom Playlist mode
        entries = []
        for u in urls:
            try:
                ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'source_address': '0.0.0.0'}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(u, download=False)
                    entries.append({
                        'title': info.get('title', 'Unknown Title'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader') or info.get('channel') or 'Unknown Channel',
                        'url': info.get('webpage_url') or u,
                        'id': info.get('id', '')
                    })
            except Exception:
                pass
        
        if not entries:
            eel.on_playlist_fetch_failed("Failed to parse any valid URLs from the list.")()
            return
            
        meta = {
            'title': 'Custom URL List',
            'entries': entries
        }
        eel.on_playlist_fetch_success(meta)()
        return

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'source_address': '0.0.0.0',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info.get('_type') != 'playlist':
            eel.on_playlist_fetch_failed("This URL is not a playlist.")()
        else:
            entries = []
            for entry in info.get('entries', []):
                if entry:
                    entries.append({
                        'title': entry.get('title', 'Unknown Title'),
                        'duration': entry.get('duration', 0),
                        'uploader': entry.get('uploader') or entry.get('channel') or 'Unknown Channel',
                        'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'id': entry.get('id', '')
                     })
            meta = {
                'title': info.get('title', 'Unknown Playlist'),
                'entries': entries
            }
            eel.on_playlist_fetch_success(meta)()
    except Exception as e:
        err_msg = str(e).split('\n')[0]
        eel.on_playlist_fetch_failed(err_msg)()

def search_youtube_worker(query):
    import eel
    if not YT_DLP_AVAILABLE:
        eel.on_search_failed("yt-dlp package is missing.")()
        return

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'source_address': '0.0.0.0',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        
        entries = []
        for entry in info.get('entries', []):
            if entry:
                entries.append({
                    'id': entry.get('id', ''),
                    'title': entry.get('title', 'Unknown Title'),
                    'uploader': entry.get('uploader') or entry.get('channel') or 'Unknown Channel',
                    'duration': entry.get('duration', 0),
                    'view_count': entry.get('view_count', 0),
                    'thumbnail': entry.get('thumbnail', '')
                })
        eel.on_search_success(entries)()
    except Exception as e:
        err_msg = str(e).split('\n')[0]
        eel.on_search_failed(err_msg)()

# Progress hooks callbacks
def single_progress_hook(d):
    import eel
    global CANCEL_DOWNLOAD, PAUSE_DOWNLOAD
    if CANCEL_DOWNLOAD:
        raise Exception("DownloadCancelledException")
        
    PAUSE_DOWNLOAD.wait()
        
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        eta = d.get('eta', 0)
        
        percent = (downloaded / total) * 100 if total > 0 else 0
        
        progress_data = {
            'percent': percent,
            'downloaded': format_bytes(downloaded),
            'total': format_bytes(total),
            'speed': f"{format_bytes(speed)}/s" if speed else "N/A",
            'eta': f"{eta}s" if eta else "N/A",
            'filename': os.path.basename(d.get('filename', ''))
        }
        eel.update_download_progress(progress_data)()
    elif d['status'] == 'finished':
        eel.on_postprocess_start()()

def download_single_worker(url, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles):
    import eel
    global CANCEL_DOWNLOAD
    CANCEL_DOWNLOAD = False
    
    audio_only = format_type == "audio"
    
    ydl_opts = {
        'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'),
        'progress_hooks': [single_progress_hook],
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 10,
        'source_address': '0.0.0.0',
    }
    
    if embed_metadata and FFMPEG_AVAILABLE:
        ydl_opts.setdefault('postprocessors', []).append({
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        })
    if embed_thumbnail and FFMPEG_AVAILABLE:
        ydl_opts.setdefault('postprocessors', []).append({
            'key': 'EmbedThumbnail',
            'already_have_thumbnail': False,
        })
    if save_thumbnail:
        ydl_opts['writethumbnail'] = True
    if download_subtitles:
        ydl_opts.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'subtitlesformat': 'srt/vtt/best',
        })
    
    if audio_only:
        ydl_opts.update({
            'format': 'bestaudio/best/b',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': ext,
                'preferredquality': '192' if 'Medium' in quality else ('320' if 'Best' in quality else '128'),
            }],
        })
    else:
        ydl_opts.update({'merge_output_format': ext})

        if quality == "Best Quality":
            ydl_opts.update({'format': 'bestvideo*+bestaudio/best/b'})
        else:
            height = quality.replace("p", "")
            ydl_opts.update({
                'format': f'bestvideo[height<=?{height}]+bestaudio/best[height<=?{height}]/bestvideo*+bestaudio/best/b'
            })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if CANCEL_DOWNLOAD:
                raise Exception("DownloadCancelledException")
            info = ydl.extract_info(url, download=True)
            
        if CANCEL_DOWNLOAD:
            eel.on_download_complete(False, "cancelled", "")()
        else:
            final_path = info.get('_filename')
            if 'requested_downloads' in info and info['requested_downloads']:
                final_path = info['requested_downloads'][0].get('filepath', final_path)
            
            size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
            save_to_history(
                info.get('title', 'Unknown Title'),
                final_path or "Unknown Location",
                f"{ext.upper()} Audio" if audio_only else f"{ext.upper()} Video",
                format_bytes(size_val)
            )
            eel.on_download_complete(True, "success", final_path)()
    except Exception as e:
        err_msg = str(e)
        if "DownloadCancelledException" in err_msg or CANCEL_DOWNLOAD:
            eel.on_download_complete(False, "cancelled", "")()
        else:
            eel.on_download_complete(False, err_msg, "")()

def playlist_progress_hook(d):
    import eel
    global CANCEL_DOWNLOAD, PAUSE_DOWNLOAD
    if CANCEL_DOWNLOAD:
        raise Exception("DownloadCancelledException")
        
    PAUSE_DOWNLOAD.wait()
        
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        grid_eta = d.get('eta', 0)
        
        percent = (downloaded / total) * 100 if total > 0 else 0
        
        progress_data = {
            'percent': percent,
            'downloaded': format_bytes(downloaded),
            'total': format_bytes(total),
            'speed': f"{format_bytes(speed)}/s" if speed else "N/A",
            'eta': f"{grid_eta}s" if grid_eta else "N/A",
            'filename': os.path.basename(d.get('filename', ''))
        }
        eel.update_playlist_progress(progress_data)()
    elif d['status'] == 'finished':
        eel.on_playlist_postprocess_start()()

def download_playlist_worker(entries, dest, format_type, quality, ext, embed_metadata, embed_thumbnail, save_thumbnail, download_subtitles):
    import eel
    global CANCEL_DOWNLOAD
    CANCEL_DOWNLOAD = False
    
    audio_only = format_type == "audio"
    total_items = len(entries)
    success_count = 0
    
    for index, entry in enumerate(entries, 1):
        if CANCEL_DOWNLOAD:
            break
            
        video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
        title = entry.get('title', 'Unknown Title')
        
        # Notify JS
        eel.on_playlist_item_start(index, total_items, title)()
        
        ydl_opts = {
            'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'),
            'progress_hooks': [playlist_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'concurrent_fragment_downloads': 10,
            'source_address': '0.0.0.0',
        }
        
        if embed_metadata and FFMPEG_AVAILABLE:
            ydl_opts.setdefault('postprocessors', []).append({
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            })
        if embed_thumbnail and FFMPEG_AVAILABLE:
            ydl_opts.setdefault('postprocessors', []).append({
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            })
        if save_thumbnail:
            ydl_opts['writethumbnail'] = True
        if download_subtitles:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'subtitlesformat': 'srt/vtt/best',
            })
        
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best/b',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': ext,
                    'preferredquality': '192' if 'Medium' in quality else ('320' if 'Best' in quality else '128'),
                }],
            })
        else:
            ydl_opts.update({'merge_output_format': ext})

            if quality == "Best Quality":
                ydl_opts.update({'format': 'bestvideo*+bestaudio/best/b'})
            else:
                height = quality.replace("p", "")
                ydl_opts.update({
                    'format': f'bestvideo[height<=?{height}]+bestaudio/best[height<=?{height}]/bestvideo*+bestaudio/best/b'
                })
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if CANCEL_DOWNLOAD:
                    raise Exception("DownloadCancelledException")
                info = ydl.extract_info(video_url, download=True)
                
            final_path = info.get('_filename')
            if 'requested_downloads' in info and info['requested_downloads']:
                final_path = info['requested_downloads'][0].get('filepath', final_path)
            
            size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
            save_to_history(
                info.get('title', title),
                final_path or "Unknown Location",
                f"{ext.upper()} Audio" if audio_only else f"{ext.upper()} Video",
                format_bytes(size_val)
            )
            success_count += 1
        except Exception as e:
            if CANCEL_DOWNLOAD or "DownloadCancelledException" in str(e):
                break
            print(f"Failed to download playlist item {index}: {e}")
            
    if CANCEL_DOWNLOAD:
        eel.on_playlist_download_complete(False, "Batch download cancelled.")()
    else:
        eel.on_playlist_download_complete(True, f"Successfully downloaded {success_count} of {total_items} items.")()


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    # Ensure dependencies from requirements.txt or fallbacks are installed
    check_and_install_dependencies()

    # Check for command line arguments (run in CLI Mode if argument exists)
    if len(sys.argv) > 1:
        # Simple CLI parser
        args = sys.argv[1:]
        urls = []
        audio_only = False
        quality = 'best'
        output_dir = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ('-a', '--audio'):
                audio_only = True
            elif arg in ('-q', '--quality') and i + 1 < len(args):
                quality = args[i+1]
                i += 1
            elif arg in ('-o', '--output') and i + 1 < len(args):
                output_dir = args[i+1]
                i += 1
            elif not arg.startswith('-'):
                urls.append(arg)
            i += 1
            
        if urls:
            cli = DownloaderCLI(urls, output_dir, audio_only, quality)
            success = cli.run()
            sys.exit(0 if success else 1)
        else:
            print("Usage Examples:")
            print("  python downloader_1.3.py <YouTube_URL>                   (Downloads best quality video)")
            print("  python downloader_1.3.py <URL1> <URL2> ...               (Batch downloads multiple URLs)")
            print("  python downloader_1.3.py <YouTube_URL> -a                (Downloads high-quality MP3 audio)")
            print("  python downloader_1.3.py <YouTube_URL> -q 720            (Downloads maximum 720p resolution video)")
            print("  python downloader_1.3.py <YouTube_URL> -o \"C:\\path\\\"    (Specifies output destination)")
            print("  python downloader_1.3.py \"search query\"                 (Searches YouTube and downloads top result)")
            print("\nOr run without arguments to launch the modern graphical desktop interface!")
            sys.exit(1)
            
    else:
        # GUI mode using Eel
        if not YT_DLP_AVAILABLE or not EEL_AVAILABLE:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Dependencies Error", 
                "Could not run: yt-dlp or eel library missing, and auto-installation failed."
            )
            sys.exit(1)

        import eel
        register_eel_exposures()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        web_path = os.path.join(script_dir, "web")
        
        eel.init(web_path)
        
        try:
            # Launch Eel app window pointing to index.html
            # size=(width, height)
            # We will use host='localhost' for safety, port=0 to bind to any free port automatically
            eel.start('index.html', size=(1080, 840), host='localhost', port=0, block=True)
        except (SystemExit, KeyboardInterrupt):
            pass
        except Exception as e:
            # Fallback alert in case of browser/socket issues
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Eel Initialization Error", 
                f"Failed to start Eel web GUI: {e}\n\nTip: Close any other instances or try running in CLI mode."
            )
            sys.exit(1)
