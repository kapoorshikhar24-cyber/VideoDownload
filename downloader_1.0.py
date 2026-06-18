#!/usr/bin/env python3
"""
Ultimate YouTube Video Downloader
A premium, feature-rich Python script that offers both:
1. A stunning, modern desktop GUI (Tkinter-based flat design with dark mode,
   separate threads to prevent freezing, progress bars, and quality options).
2. A beautiful, colored Command Line Interface (CLI) for power users.

Author: Antigravity AI
Version: 1.1.0
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

# Try to import ttk for better styling, standard tkinter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Global variables for auto-installation tracking
DEPENDENCIES_CHECKED = False

def check_and_install_dependencies():
    """
    Checks if necessary third-party libraries (specifically yt-dlp) are installed.
    If not, offers to install them automatically.
    """
    global DEPENDENCIES_CHECKED
    if DEPENDENCIES_CHECKED:
        return True

    try:
        import yt_dlp
        DEPENDENCIES_CHECKED = True
        return True
    except ImportError:
        print("[*] yt-dlp is not installed. Attempting to install it automatically...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Verify import again
            import yt_dlp
            print("[+] Successfully installed yt-dlp!")
            DEPENDENCIES_CHECKED = True
            return True
        except Exception as e:
            print(f"[-] Failed to automatically install yt-dlp: {e}")
            print("[-] Please run 'pip install yt-dlp' manually.")
            return False

# Run dependency check right away
YT_DLP_AVAILABLE = check_and_install_dependencies()

if YT_DLP_AVAILABLE:
    import yt_dlp
else:
    # Minimal fallback structure so the script compiles and runs GUI to display error
    class DummyYTDLP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            raise ImportError("yt-dlp is not installed. Please install it with 'pip install yt-dlp'")
    yt_dlp = type('DummyModule', (), {'YoutubeDL': DummyYTDLP})()

# Try to import Pillow for thumbnail rendering in GUI (Optional)
PILLOW_AVAILABLE = False
try:
    from PIL import Image, ImageTk
    PILLOW_AVAILABLE = True
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
    """Checks if ffmpeg is available on the system path."""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
        return True
    except Exception:
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
    # Add new entry at the beginning
    history.insert(0, {
        "title": title,
        "path": file_path,
        "format": format_type,
        "size": size,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    # Keep last 100 downloads
    history = history[:100]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# ==============================================================================
# 1. COMMAND LINE INTERFACE (CLI) MODE
# ==============================================================================
class DownloaderCLI:
    def __init__(self, url, output_dir=None, audio_only=False, quality='best'):
        self.url = url
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

        # Support search prefix if URL is not a direct web address
        actual_url = self.url
        if not self.url.startswith("http://") and not self.url.startswith("https://"):
            print(f"[*] Searching YouTube for query: '{self.url}'...")
            actual_url = f"ytsearch1:{self.url}"

        print(f"[*] Extracting video info...")
        
        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'no_warnings': True,
            'concurrent_fragment_downloads': 30,
            'http_chunk_size': 10485760,
        }
        
        if self.audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            if self.quality == 'best':
                ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
            else:
                ydl_opts.update({
                    'format': f'bestvideo[height<={self.quality}]+bestaudio/best[height<={self.quality}]/best'
                })

        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(actual_url, download=False)
            
            # Handle search results
            if 'entries' in info and info.get('_type') == 'playlist' and actual_url.startswith("ytsearch"):
                if not info['entries']:
                    print("\033[91m[-] No search results found.\033[0m")
                    return False
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
                return success_count > 0

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
                
            print("\033[92m[+] All Done! Enjoy your file.\033[0m\n")
            return True
            
        except Exception as e:
            print(f"\n\033[91m[-] Error occurred: {e}\033[0m")
            print("\033[93m[!] Tip: If download fails with merge errors, you may need 'ffmpeg' installed on your system.\033[0m\n")
            return False


# ==============================================================================
# Helper UI Elements
# ==============================================================================
class TabButton(tk.Label):
    """Bespoke styled tab button with hover and active states."""
    def __init__(self, parent, text, command, colors, **kwargs):
        super().__init__(
            parent,
            text=text,
            bg=colors['card'],
            fg=colors['text_muted'],
            font=('Segoe UI', 10, 'bold'),
            padx=18,
            pady=10,
            cursor='hand2',
            relief='flat',
            **kwargs
        )
        self.command = command
        self.colors = colors
        self.is_active = False
        
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
    def on_hover(self, e):
        if not self.is_active:
            self.configure(bg='#2A2A2A', fg=self.colors['text'])
            
    def on_leave(self, e):
        if not self.is_active:
            self.configure(bg=self.colors['card'], fg=self.colors['text_muted'])
            
    def on_click(self, e):
        self.command()
        
    def set_active(self, active):
        self.is_active = active
        if active:
            self.configure(bg=self.colors['accent'], fg=self.colors['text'])
        else:
            self.configure(bg=self.colors['card'], fg=self.colors['text_muted'])


class ScrollableFrame(ttk.Frame):
    """Custom scrollable frame container."""
    def __init__(self, container, colors, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, bg=colors['bg'], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style='TFrame')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scrolling bindings (only when mouse is over canvas)
        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def _on_mousewheel(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ==============================================================================
# 2. MODERN GRAPHICAL USER INTERFACE (GUI) MODE
# ==============================================================================
class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity - Ultimate YouTube Downloader")
        self.root.geometry("900x750")
        self.root.minsize(850, 680)
        
        # Color Palette - Premium YouTube-Inspired Cyberpunk Dark Mode
        self.colors = {
            'bg': '#121212',         # Ultra dark background
            'card': '#1E1E1E',       # Lighter dark for cards
            'accent': '#FF3E3E',     # Neon Red / YouTube Red
            'accent_hover': '#E50914',
            'text': '#FFFFFF',       # White text
            'text_muted': '#AAAAAA', # Gray text
            'border': '#2A2A2A',     # Dark gray border
            'green': '#00E676',      # Neon Green for success
            'blue': '#2979FF',       # Neon Blue for info
            'progress_bg': '#333333'
        }
        
        # Application States
        self.output_dir = tk.StringVar(value=get_default_download_dir())
        
        # Options States
        self.embed_metadata = tk.BooleanVar(value=True)
        self.embed_thumbnail = tk.BooleanVar(value=True)
        self.download_subtitles = tk.BooleanVar(value=False)
        self.save_thumbnail_file = tk.BooleanVar(value=False)
        
        self.current_video_info = None
        self.current_playlist_info = None
        
        self.download_thread = None
        self.fetching_thread = None
        self.search_thread = None
        self.cancel_download = False
        self.thumbnail_image = None
        
        # Search thumbnails caching list to keep Image references in memory
        self.search_thumbnail_images = []
        
        # Playlist checkbox items mapping
        self.playlist_checkbox_vars = []
        self.playlist_checkbox_widgets = []
        
        # Setup modern dark style
        self.setup_styles()
        self.build_ui()
        
        # Load history
        self.root.after(100, self.refresh_history_ui)
        # Auto-paste from clipboard if it contains a YouTube URL
        self.root.after(500, self.auto_paste_url)

    def setup_styles(self):
        """Sets up custom styles and fonts for a premium aesthetic."""
        self.root.configure(bg=self.colors['bg'])
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure overall style colors
        self.style.configure('.', background=self.colors['bg'], foreground=self.colors['text'])
        
        # TFrame styling
        self.style.configure('TFrame', background=self.colors['bg'])
        self.style.configure('Card.TFrame', background=self.colors['card'], relief='flat')
        
        # TButton styling
        self.style.configure(
            'Accent.TButton',
            background=self.colors['accent'],
            foreground=self.colors['text'],
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors['accent_hover'],
            font=('Segoe UI', 10, 'bold'),
            padding=(20, 10)
        )
        self.style.map(
            'Accent.TButton',
            background=[('active', self.colors['accent_hover'])],
            foreground=[('active', self.colors['text'])]
        )
        
        self.style.configure(
            'Secondary.TButton',
            background=self.colors['border'],
            foreground=self.colors['text'],
            borderwidth=1,
            relief='flat',
            font=('Segoe UI', 10),
            padding=(12, 8)
        )
        self.style.map(
            'Secondary.TButton',
            background=[('active', '#3A3A3A')]
        )
        
        # Combobox styling
        self.style.configure(
            'TCombobox',
            fieldbackground=self.colors['card'],
            background=self.colors['border'],
            foreground=self.colors['text'],
            arrowcolor=self.colors['text'],
            font=('Segoe UI', 10)
        )
        
        # Labels
        self.style.configure('TLabel', background=self.colors['bg'], foreground=self.colors['text'], font=('Segoe UI', 10))
        self.style.configure('Card.TLabel', background=self.colors['card'], foreground=self.colors['text'], font=('Segoe UI', 10))
        self.style.configure('Header.TLabel', background=self.colors['bg'], foreground=self.colors['text'], font=('Segoe UI', 18, 'bold'))
        self.style.configure('SubHeader.TLabel', background=self.colors['bg'], foreground=self.colors['text_muted'], font=('Segoe UI', 9))
        self.style.configure('Title.Card.TLabel', background=self.colors['card'], foreground=self.colors['text'], font=('Segoe UI', 12, 'bold'))

    def build_ui(self):
        """Assembles the premium tabbed user interface."""
        # --- Top Window Margin ---
        main_container = ttk.Frame(self.root, padding=25)
        main_container.pack(fill='both', expand=True)
        
        # --- Header Section ---
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = ttk.Label(
            header_frame, 
            text="ANTIGRAVITY", 
            font=('Segoe UI', 24, 'bold'),
            foreground=self.colors['accent']
        )
        title_label.pack(side='left')
        
        subtitle_label = ttk.Label(
            header_frame, 
            text=" |  Ultimate YouTube Downloader & Client", 
            font=('Segoe UI', 14, 'italic'),
            foreground=self.colors['text_muted']
        )
        subtitle_label.pack(side='left', padx=5, pady=(8, 0))
        
        # Check FFmpeg and add a small warning if missing
        if not FFMPEG_AVAILABLE:
            ffmpeg_warning = ttk.Label(
                header_frame,
                text="[!] FFmpeg missing (Merging/MP3 encoding disabled)",
                font=('Segoe UI', 9, 'bold'),
                foreground=self.colors['accent']
            )
            ffmpeg_warning.pack(side='right', pady=(10, 0))
        
        # --- Custom Tab Selector Bar ---
        self.tab_bar = ttk.Frame(main_container)
        self.tab_bar.pack(fill='x', pady=(0, 20))
        
        self.tab_buttons = {}
        tabs = [
            ("single", "Single Download"),
            ("playlist", "Playlist Batch"),
            ("search", "YouTube Search"),
            ("history", "Library History")
        ]
        
        for tab_id, tab_name in tabs:
            btn = TabButton(
                self.tab_bar, 
                text=tab_name, 
                command=lambda tid=tab_id: self.show_tab(tid),
                colors=self.colors
            )
            btn.pack(side='left', padx=(0, 5))
            self.tab_buttons[tab_id] = btn

        # --- Content Area Container ---
        self.tab_container = ttk.Frame(main_container)
        self.tab_container.pack(fill='both', expand=True)
        
        # Instantiate the 4 tab frames
        self.tab_frames = {
            "single": ttk.Frame(self.tab_container),
            "playlist": ttk.Frame(self.tab_container),
            "search": ttk.Frame(self.tab_container),
            "history": ttk.Frame(self.tab_container)
        }
        
        # Build contents inside each tab frame
        self.build_single_tab_ui()
        self.build_playlist_tab_ui()
        self.build_search_tab_ui()
        self.build_history_tab_ui()
        
        # Show default tab
        self.show_tab("single")
        
        # --- Persistent Status Bar ---
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill='x', pady=(15, 0))
        self.status_bar = ttk.Label(
            status_frame, 
            text="Ready", 
            style='SubHeader.TLabel',
            font=('Segoe UI', 10)
        )
        self.status_bar.pack(side='left', fill='x', expand=True)

    def show_tab(self, tab_id):
        """Displays selected tab frame and hides all others."""
        for tid, frame in self.tab_frames.items():
            frame.pack_forget()
            self.tab_buttons[tid].set_active(False)
            
        self.tab_frames[tab_id].pack(fill='both', expand=True)
        self.tab_buttons[tab_id].set_active(True)

    # ==============================================================================
    # TAB 1: SINGLE DOWNLOAD
    # ==============================================================================
    def build_single_tab_ui(self):
        frame = self.tab_frames["single"]
        
        # URL Input Card
        url_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        url_card.pack(fill='x', pady=(0, 20))
        
        url_lbl = ttk.Label(url_card, text="YouTube Video URL", style='Title.Card.TLabel')
        url_lbl.pack(anchor='w', pady=(0, 8))
        
        input_row = ttk.Frame(url_card)
        input_row.configure(style='Card.TFrame')
        input_row.pack(fill='x')
        
        self.url_entry = tk.Entry(
            input_row,
            bg='#2C2C2C',
            fg='#FFFFFF',
            insertbackground='#FFFFFF',
            relief='flat',
            font=('Segoe UI', 11),
            bd=8
        )
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.url_entry.bind('<KeyRelease>', self.on_url_modified)
        
        self.paste_btn = ttk.Button(
            input_row, 
            text="Paste", 
            style='Secondary.TButton', 
            command=self.paste_from_clipboard
        )
        self.paste_btn.pack(side='left', padx=(0, 10))
        
        self.fetch_btn = ttk.Button(
            input_row, 
            text="Analyze Link", 
            style='Accent.TButton', 
            command=self.start_fetching_metadata
        )
        self.fetch_btn.pack(side='right')

        # Details container (Metadata card & Settings side-by-side or stacked)
        self.details_container = ttk.Frame(frame)
        self.details_container.pack(fill='both', expand=True, pady=(0, 20))
        
        self.placeholder_card = ttk.Frame(self.details_container, style='Card.TFrame', padding=40)
        self.placeholder_card.pack(fill='both', expand=True)
        
        placeholder_lbl = ttk.Label(
            self.placeholder_card,
            text="Paste a YouTube URL and click 'Analyze Link'\nto reveal video formats and download options.",
            font=('Segoe UI', 11),
            foreground=self.colors['text_muted'],
            justify='center',
            style='Card.TLabel'
        )
        placeholder_lbl.pack(expand=True)

        # Video Details Card (Initially hidden)
        self.video_card = ttk.Frame(self.details_container, style='Card.TFrame', padding=15)
        
        self.thumb_canvas = tk.Canvas(
            self.video_card, 
            bg='#181818', 
            highlightthickness=1, 
            highlightbackground=self.colors['border'], 
            width=240, 
            height=135
        )
        self.thumb_canvas.pack(side='left', anchor='nw', padx=(0, 15))
        self.draw_thumbnail_placeholder("No Video Loaded")
        
        self.meta_frame = ttk.Frame(self.video_card, style='Card.TFrame')
        self.meta_frame.pack(side='left', fill='both', expand=True)
        
        self.vid_title = ttk.Label(self.meta_frame, text="Video Title", style='Title.Card.TLabel', wraplength=450)
        self.vid_title.pack(anchor='w', pady=(0, 6))
        
        self.vid_channel = ttk.Label(self.meta_frame, text="Channel: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.vid_channel.pack(anchor='w', pady=(0, 4))
        
        self.vid_duration = ttk.Label(self.meta_frame, text="Duration: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.vid_duration.pack(anchor='w', pady=(0, 4))
        
        self.vid_views = ttk.Label(self.meta_frame, text="Views: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.vid_views.pack(anchor='w')

        # Settings Card (Initially hidden)
        self.options_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        
        dest_lbl = ttk.Label(self.options_card, text="Save To:", style='Title.Card.TLabel')
        dest_lbl.pack(anchor='w', pady=(0, 8))
        
        dest_row = ttk.Frame(self.options_card, style='Card.TFrame')
        dest_row.pack(fill='x', pady=(0, 12))
        
        self.dest_entry = tk.Entry(
            dest_row,
            textvariable=self.output_dir,
            bg='#2C2C2C',
            fg='#FFFFFF',
            relief='flat',
            font=('Segoe UI', 10),
            bd=6
        )
        self.dest_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.browse_btn = ttk.Button(
            dest_row,
            text="Browse...",
            style='Secondary.TButton',
            command=self.browse_directory
        )
        self.browse_btn.pack(side='right')
        
        # Download Format Options
        format_row = ttk.Frame(self.options_card, style='Card.TFrame')
        format_row.pack(fill='x', pady=(0, 12))
        
        type_lbl = ttk.Label(format_row, text="Format Type:", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        type_lbl.pack(side='left', padx=(0, 10))
        
        self.format_type = tk.StringVar(value="video")
        self.video_radio = tk.Radiobutton(
            format_row, 
            text="Video (MP4)", 
            variable=self.format_type, 
            value="video",
            bg=self.colors['card'],
            fg=self.colors['text'],
            selectcolor=self.colors['bg'],
            activebackground=self.colors['card'],
            activeforeground=self.colors['text'],
            font=('Segoe UI', 10),
            command=self.on_format_type_changed
        )
        self.video_radio.pack(side='left', padx=(0, 15))
        
        self.audio_radio = tk.Radiobutton(
            format_row, 
            text="Audio (MP3)", 
            variable=self.format_type, 
            value="audio",
            bg=self.colors['card'],
            fg=self.colors['text'],
            selectcolor=self.colors['bg'],
            activebackground=self.colors['card'],
            activeforeground=self.colors['text'],
            font=('Segoe UI', 10),
            command=self.on_format_type_changed
        )
        self.audio_radio.pack(side='left', padx=(0, 20))
        
        self.quality_lbl = ttk.Label(format_row, text="Quality:", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        self.quality_lbl.pack(side='left', padx=(0, 10))
        
        self.quality_var = tk.StringVar(value="Best Quality")
        self.quality_combobox = ttk.Combobox(
            format_row, 
            textvariable=self.quality_var, 
            state='readonly',
            width=18,
            style='TCombobox'
        )
        self.quality_combobox['values'] = ("Best Quality", "1080p", "720p", "480p", "360p")
        self.quality_combobox.pack(side='left')

        # Advanced Settings Options
        adv_row = ttk.Frame(self.options_card, style='Card.TFrame')
        adv_row.pack(fill='x')
        
        adv_lbl = ttk.Label(adv_row, text="Extra Controls:", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        adv_lbl.pack(side='left', padx=(0, 15))
        
        self.chk_meta = tk.Checkbutton(
            adv_row, text="Embed Metadata", variable=self.embed_metadata,
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 9), state='normal' if FFMPEG_AVAILABLE else 'disabled'
        )
        self.chk_meta.pack(side='left', padx=(0, 15))
        
        self.chk_thumb = tk.Checkbutton(
            adv_row, text="Embed Thumbnail", variable=self.embed_thumbnail,
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 9), state='normal' if FFMPEG_AVAILABLE else 'disabled'
        )
        self.chk_thumb.pack(side='left', padx=(0, 15))
        
        self.chk_sub = tk.Checkbutton(
            adv_row, text="Download Subtitles (EN)", variable=self.download_subtitles,
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 9)
        )
        self.chk_sub.pack(side='left', padx=(0, 15))
        
        self.chk_save_thumb = tk.Checkbutton(
            adv_row, text="Save Thumbnail Image", variable=self.save_thumbnail_file,
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 9)
        )
        self.chk_save_thumb.pack(side='left')

        # Download Panel (Progress bars - Initially hidden)
        self.download_panel = ttk.Frame(frame, style='Card.TFrame', padding=15)
        
        self.dl_status_lbl = ttk.Label(self.download_panel, text="Downloading...", style='Title.Card.TLabel')
        self.dl_status_lbl.pack(anchor='w', pady=(0, 8))
        
        self.progress_canvas = tk.Canvas(
            self.download_panel,
            bg=self.colors['progress_bg'],
            height=8,
            highlightthickness=0
        )
        self.progress_canvas.pack(fill='x', pady=(0, 8))
        self.progress_bar_rect = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill=self.colors['accent'], width=0)
        
        stats_row = ttk.Frame(self.download_panel, style='Card.TFrame')
        stats_row.pack(fill='x')
        
        self.percent_lbl = ttk.Label(stats_row, text="0.0%", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        self.percent_lbl.pack(side='left')
        
        self.speed_lbl = ttk.Label(stats_row, text="Speed: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.speed_lbl.pack(side='left', padx=30)
        
        self.eta_lbl = ttk.Label(stats_row, text="ETA: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.eta_lbl.pack(side='left')
        
        self.size_lbl = ttk.Label(stats_row, text="-- / --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.size_lbl.pack(side='right')

        # Bottom row action button
        self.single_action_row = ttk.Frame(frame)
        self.single_action_row.pack(fill='x', pady=(10, 0))
        
        self.cancel_btn = ttk.Button(
            self.single_action_row,
            text="Cancel Download",
            style='Secondary.TButton',
            command=self.cancel_active_download
        )
        
        self.download_btn = ttk.Button(
            self.single_action_row,
            text="Download Video Now",
            style='Accent.TButton',
            command=self.start_download
        )
        self.download_btn.pack(side='right')
        self.download_btn.configure(state='disabled')

    def draw_thumbnail_placeholder(self, text):
        """Draws a beautiful cyberpunk placeholder in the single thumbnail space."""
        self.thumb_canvas.delete("all")
        self.thumb_canvas.create_rectangle(0, 0, 240, 135, fill='#1A1A1A', outline=self.colors['border'], width=2)
        self.thumb_canvas.create_polygon(0, 0, 30, 0, 0, 30, fill=self.colors['accent'])
        self.thumb_canvas.create_polygon(105, 50, 140, 68, 105, 86, fill='#444444', outline='#666666', width=1)
        self.thumb_canvas.create_text(
            120, 105, 
            text=text, 
            fill=self.colors['text_muted'], 
            font=('Segoe UI', 9, 'bold'),
            width=220,
            justify='center'
        )

    def auto_paste_url(self):
        """Automatically checks clipboard and pastes URL if found."""
        try:
            clipboard = self.root.clipboard_get()
            if clipboard and (clipboard.startswith("http://") or clipboard.startswith("https://")):
                if "list=" in clipboard:
                    self.playlist_url_entry.delete(0, tk.END)
                    self.playlist_url_entry.insert(0, clipboard.strip())
                    self.show_tab("playlist")
                    self.update_status("Playlist URL detected and pasted into Playlist tab.", 'blue')
                else:
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, clipboard.strip())
                    self.show_tab("single")
                    self.update_status("Media URL detected and pasted.", 'blue')
        except Exception:
            pass

    def on_url_modified(self, event=None):
        if self.current_video_info:
            if self.url_entry.get().strip() != self.current_video_info.get('original_url', ''):
                self.reset_ui_analysis()

    def reset_ui_analysis(self):
        self.current_video_info = None
        self.download_btn.configure(state='disabled')
        self.video_card.pack_forget()
        self.options_card.pack_forget()
        self.placeholder_card.pack(fill='both', expand=True)
        self.draw_thumbnail_placeholder("No Video Loaded")
        self.update_status("Ready")

    def paste_from_clipboard(self):
        try:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.root.clipboard_get().strip())
            self.on_url_modified()
        except Exception:
            messagebox.showerror("Error", "Could not paste from clipboard.")

    def browse_directory(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir.get())
        if folder:
            self.output_dir.set(folder)

    def on_format_type_changed(self):
        if self.format_type.get() == "audio":
            self.quality_lbl.configure(text="Audio Quality:")
            self.quality_combobox['values'] = ("Best (320kbps)", "Medium (192kbps)", "Low (128kbps)")
            self.quality_var.set("Medium (192kbps)")
        else:
            self.quality_lbl.configure(text="Quality / Resolution:")
            self.quality_combobox['values'] = ("Best Quality", "1080p", "720p", "480p", "360p")
            self.quality_var.set("Best Quality")

    def update_status(self, text, color_key=None):
        self.status_bar.configure(text=text)
        if color_key and color_key in self.colors:
            self.status_bar.configure(foreground=self.colors[color_key])
        else:
            self.status_bar.configure(foreground=self.colors['text_muted'])

    def start_fetching_metadata(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a valid media URL first!")
            return

        self.reset_ui_analysis()
        self.fetch_btn.configure(state='disabled')
        self.update_status("Connecting to YouTube & analyzing media...", 'blue')
        self.draw_thumbnail_placeholder("Analyzing video details...")

        self.url_entry.configure(state='disabled')
        self.paste_btn.configure(state='disabled')

        self.fetching_thread = threading.Thread(target=self.fetch_metadata_worker, args=(url,), daemon=True)
        self.fetching_thread.start()

    def fetch_metadata_worker(self, url):
        if not YT_DLP_AVAILABLE:
            self.root.after(0, self.on_fetch_failed, "yt-dlp package is missing.")
            return

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                info['original_url'] = url
            self.root.after(0, self.on_fetch_success, info)
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            self.root.after(0, self.on_fetch_failed, f"Failed to fetch: {err_msg}")

    def on_fetch_success(self, info):
        self.current_video_info = info
        self.fetch_btn.configure(state='normal')
        self.url_entry.configure(state='normal')
        self.paste_btn.configure(state='normal')
        
        # Hide placeholder, display options cards
        self.placeholder_card.pack_forget()
        self.video_card.pack(fill='x', pady=(0, 15))
        self.options_card.pack(fill='x', pady=(0, 15))
        self.download_btn.configure(state='normal')
        
        # Update metadata
        title = info.get('title', 'Unknown Title')
        channel = info.get('uploader', 'Unknown Channel')
        duration = format_duration(info.get('duration'))
        views = f"{info.get('view_count', 0):,}" if info.get('view_count') else "N/A"
        
        self.vid_title.configure(text=title)
        self.vid_channel.configure(text=f"Channel: {channel}")
        self.vid_duration.configure(text=f"Duration: {duration}")
        self.vid_views.configure(text=f"Views: {views}")
        
        # Load thumbnail in background
        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            threading.Thread(target=self.load_thumbnail_image, args=(thumbnail_url,), daemon=True).start()
        else:
            self.draw_thumbnail_placeholder("No Thumbnail")

        self.on_format_type_changed()
        self.update_status("Video details loaded successfully!", 'green')

    def on_fetch_failed(self, error_message):
        self.fetch_btn.configure(state='normal')
        self.url_entry.configure(state='normal')
        self.paste_btn.configure(state='normal')
        self.reset_ui_analysis()
        self.draw_thumbnail_placeholder("Analysis Failed")
        messagebox.showerror("Metadata Extraction Failed", f"An error occurred while fetching video info:\n\n{error_message}")

    def load_thumbnail_image(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                image_data = response.read()

            if PILLOW_AVAILABLE:
                import io
                image = Image.open(io.BytesIO(image_data))
                image = image.resize((240, 135), Image.Resampling.LANCZOS)
                
                self.thumbnail_image = ImageTk.PhotoImage(image)
                
                def update_canvas():
                    self.thumb_canvas.delete("all")
                    self.thumb_canvas.create_image(120, 68, image=self.thumbnail_image)
                    self.thumb_canvas.create_polygon(0, 0, 20, 0, 0, 20, fill=self.colors['accent'])
                
                self.root.after(0, update_canvas)
            else:
                self.root.after(0, lambda: self.draw_thumbnail_placeholder("PIL Pillow Required"))
        except Exception:
            self.root.after(0, lambda: self.draw_thumbnail_placeholder("Thumbnail Error"))

    def start_download(self):
        if not self.current_video_info:
            return
            
        url = self.current_video_info.get('webpage_url') or self.url_entry.get().strip()
        save_path = self.output_dir.get()
        
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Invalid download directory: {e}")
                return
                 
        self.cancel_download = False
        self.download_btn.pack_forget()
        self.cancel_btn.pack(side='right')
        
        self.video_card.pack_forget()
        self.options_card.pack_forget()
        self.download_panel.pack(fill='x', pady=(0, 20))
        
        self.url_entry.configure(state='disabled')
        self.paste_btn.configure(state='disabled')
        self.fetch_btn.configure(state='disabled')
        
        # Reset progress bar
        self.progress_canvas.coords(self.progress_bar_rect, 0, 0, 0, 8)
        self.percent_lbl.configure(text="0.0%")
        self.speed_lbl.configure(text="Speed: Starting...")
        self.eta_lbl.configure(text="ETA: Calculating...")
        self.size_lbl.configure(text="-- / --")
        
        self.dl_status_lbl.configure(text=f"Downloading: {self.current_video_info.get('title', 'Video')}")
        self.update_status("Starting download process...", 'blue')
        
        self.download_thread = threading.Thread(
            target=self.download_worker, 
            args=(url, save_path), 
            daemon=True
        )
        self.download_thread.start()

    def download_worker(self, url, save_path):
        audio_only = self.format_type.get() == "audio"
        quality = self.quality_var.get()
        
        ydl_opts = {
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            'progress_hooks': [self.yt_dlp_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'concurrent_fragment_downloads': 30,
            'http_chunk_size': 10485760,
        }
        
        # Apply advanced settings
        if self.embed_metadata.get() and FFMPEG_AVAILABLE:
            ydl_opts.setdefault('postprocessors', []).append({
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            })
        if self.embed_thumbnail.get() and FFMPEG_AVAILABLE:
            ydl_opts.setdefault('postprocessors', []).append({
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            })
        if self.save_thumbnail_file.get():
            ydl_opts['writethumbnail'] = True
        if self.download_subtitles.get():
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'subtitlesformat': 'srt/vtt/best',
            })
        
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192' if 'Medium' in quality else ('320' if 'Best' in quality else '128'),
                }],
            })
        else:
            if quality == "Best Quality":
                ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
            else:
                height = quality.replace("p", "")
                ydl_opts.update({
                    'format': f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
                })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if self.cancel_download:
                    raise Exception("DownloadCancelledException")
                
                info = ydl.extract_info(url, download=True)
                
            if self.cancel_download:
                self.root.after(0, self.on_download_complete, False, "Download cancelled by user.")
            else:
                # Get final file path to save to history
                final_path = info.get('_filename')
                if 'requested_downloads' in info and info['requested_downloads']:
                    final_path = info['requested_downloads'][0].get('filepath', final_path)
                
                size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
                save_to_history(
                    info.get('title', 'Unknown Title'),
                    final_path or "Unknown Location",
                    'MP3 Audio' if audio_only else 'MP4 Video',
                    format_bytes(size_val)
                )
                self.root.after(0, self.refresh_history_ui)
                self.root.after(0, self.on_download_complete, True, "Download completed successfully!")
                
        except Exception as e:
            err_msg = str(e)
            if "DownloadCancelledException" in err_msg or self.cancel_download:
                self.root.after(0, self.on_download_complete, False, "Download cancelled.")
            else:
                self.root.after(0, self.on_download_complete, False, err_msg)

    def yt_dlp_progress_hook(self, d):
        if self.cancel_download:
            raise Exception("DownloadCancelledException")
            
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            percent = (downloaded / total) * 100 if total > 0 else 0
            
            progress_data = {
                'percent': percent,
                'downloaded': downloaded,
                'total': total,
                'speed': speed,
                'eta': eta,
                'filename': os.path.basename(d.get('filename', ''))
            }
            
            self.root.after(0, self.update_download_progress_ui, progress_data)
            
        elif d['status'] == 'finished':
            self.root.after(0, self.update_status, "Post-processing/Merging streams...", 'blue')

    def update_download_progress_ui(self, data):
        if self.cancel_download:
            return
            
        percent = data['percent']
        speed = data['speed']
        eta = data['eta']
        downloaded = data['downloaded']
        total = data['total']
        
        canvas_width = self.progress_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 750
            
        bar_width = int(canvas_width * (percent / 100))
        self.progress_canvas.coords(self.progress_bar_rect, 0, 0, bar_width, 8)
        
        self.percent_lbl.configure(text=f"{percent:.1f}%")
        self.speed_lbl.configure(text=f"Speed: {format_bytes(speed)}/s" if speed else "Speed: --")
        self.eta_lbl.configure(text=f"ETA: {format_duration(eta)}" if eta else "ETA: --")
        self.size_lbl.configure(text=f"{format_bytes(downloaded)} / {format_bytes(total)}")
        self.update_status(f"Downloading stream: {data['filename'][:50]}...", 'blue')

    def cancel_active_download(self):
        if messagebox.askyesno("Cancel Download", "Are you sure you want to cancel the download?"):
            self.cancel_download = True
            self.update_status("Cancelling download...", 'accent')

    def on_download_complete(self, success, message):
        self.cancel_btn.pack_forget()
        self.download_btn.pack(side='right')
        self.download_panel.pack_forget()
        
        self.video_card.pack(fill='x', pady=(0, 15))
        self.options_card.pack(fill='x', pady=(0, 15))
        
        self.url_entry.configure(state='normal')
        self.paste_btn.configure(state='normal')
        self.fetch_btn.configure(state='normal')
        
        if success:
            self.update_status("Download complete!", 'green')
            messagebox.showinfo("Success", "Video downloaded successfully!\n\nLocation:\n" + self.output_dir.get())
        else:
            self.update_status("Download failed.", 'accent')
            if "cancelled" in message.lower():
                messagebox.showinfo("Cancelled", "Download was successfully cancelled.")
            else:
                messagebox.showerror(
                    "Download Failed",
                    f"An error occurred during download:\n\n{message}\n\n"
                    "Tip: High resolution (1080p+) downloads may require 'ffmpeg' to merge video/audio."
                )

    # ==============================================================================
    # TAB 2: PLAYLIST BATCH
    # ==============================================================================
    def build_playlist_tab_ui(self):
        frame = self.tab_frames["playlist"]
        
        # Playlist URL Input Card
        p_url_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        p_url_card.pack(fill='x', pady=(0, 15))
        
        p_url_lbl = ttk.Label(p_url_card, text="YouTube Playlist URL", style='Title.Card.TLabel')
        p_url_lbl.pack(anchor='w', pady=(0, 8))
        
        p_input_row = ttk.Frame(p_url_card, style='Card.TFrame')
        p_input_row.pack(fill='x')
        
        self.playlist_url_entry = tk.Entry(
            p_input_row,
            bg='#2C2C2C',
            fg='#FFFFFF',
            insertbackground='#FFFFFF',
            relief='flat',
            font=('Segoe UI', 11),
            bd=8
        )
        self.playlist_url_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        p_paste_btn = ttk.Button(
            p_input_row, 
            text="Paste", 
            style='Secondary.TButton', 
            command=lambda: [self.playlist_url_entry.delete(0, tk.END), self.playlist_url_entry.insert(0, self.root.clipboard_get().strip())]
        )
        p_paste_btn.pack(side='left', padx=(0, 10))
        
        self.playlist_fetch_btn = ttk.Button(
            p_input_row, 
            text="Analyze Playlist", 
            style='Accent.TButton', 
            command=self.start_fetching_playlist
        )
        self.playlist_fetch_btn.pack(side='right')

        # Playlist Content & Checklist Layout
        self.playlist_details_container = ttk.Frame(frame)
        self.playlist_details_container.pack(fill='both', expand=True, pady=(0, 15))
        
        self.playlist_placeholder = ttk.Frame(self.playlist_details_container, style='Card.TFrame', padding=40)
        self.playlist_placeholder.pack(fill='both', expand=True)
        
        p_place_lbl = ttk.Label(
            self.playlist_placeholder,
            text="Analyze a playlist link to select videos for batch download.",
            font=('Segoe UI', 11),
            foreground=self.colors['text_muted'],
            justify='center',
            style='Card.TLabel'
        )
        p_place_lbl.pack(expand=True)

        # Playlist Meta + Checklist Card (Initially hidden)
        self.playlist_view_card = ttk.Frame(self.playlist_details_container, style='Card.TFrame', padding=15)
        
        p_info_header = ttk.Frame(self.playlist_view_card, style='Card.TFrame')
        p_info_header.pack(fill='x', pady=(0, 10))
        
        self.playlist_title_lbl = ttk.Label(p_info_header, text="Playlist Title: --", style='Title.Card.TLabel')
        self.playlist_title_lbl.pack(anchor='w')
        
        self.playlist_count_lbl = ttk.Label(p_info_header, text="Videos Found: 0", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.playlist_count_lbl.pack(anchor='w', pady=(3, 10))
        
        # Batch Select Buttons
        select_row = ttk.Frame(p_info_header, style='Card.TFrame')
        select_row.pack(fill='x')
        
        select_all_btn = ttk.Button(
            select_row, text="Select All", style='Secondary.TButton', padding=(8, 4),
            command=lambda: self.toggle_all_playlist_checkboxes(True)
        )
        select_all_btn.pack(side='left', padx=(0, 8))
        
        select_none_btn = ttk.Button(
            select_row, text="Select None", style='Secondary.TButton', padding=(8, 4),
            command=lambda: self.toggle_all_playlist_checkboxes(False)
        )
        select_none_btn.pack(side='left')

        # Scrollable checklist container
        self.playlist_scroll_frame = ScrollableFrame(self.playlist_view_card, self.colors)
        self.playlist_scroll_frame.pack(fill='both', expand=True, pady=10)

        # Settings Card for Playlist (Initially hidden)
        self.playlist_options_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        
        p_dest_row = ttk.Frame(self.playlist_options_card, style='Card.TFrame')
        p_dest_row.pack(fill='x', pady=(0, 12))
        
        ttk.Label(p_dest_row, text="Save To: ", style='Card.TLabel', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 8))
        self.p_dest_entry = tk.Entry(
            p_dest_row,
            textvariable=self.output_dir,
            bg='#2C2C2C',
            fg='#FFFFFF',
            relief='flat',
            font=('Segoe UI', 10),
            bd=6
        )
        self.p_dest_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        p_browse_btn = ttk.Button(p_dest_row, text="Browse...", style='Secondary.TButton', command=self.browse_directory)
        p_browse_btn.pack(side='right')

        # Playlist Format Rows
        p_format_row = ttk.Frame(self.playlist_options_card, style='Card.TFrame')
        p_format_row.pack(fill='x', pady=(0, 10))
        
        ttk.Label(p_format_row, text="Format Type:", style='Card.TLabel', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 10))
        
        self.p_format_type = tk.StringVar(value="video")
        self.p_video_radio = tk.Radiobutton(
            p_format_row, text="Video (MP4)", variable=self.p_format_type, value="video",
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 10), command=self.on_playlist_format_type_changed
        )
        self.p_video_radio.pack(side='left', padx=(0, 15))
        
        self.p_audio_radio = tk.Radiobutton(
            p_format_row, text="Audio (MP3)", variable=self.p_format_type, value="audio",
            bg=self.colors['card'], fg=self.colors['text'], selectcolor=self.colors['bg'],
            activebackground=self.colors['card'], activeforeground=self.colors['text'],
            font=('Segoe UI', 10), command=self.on_playlist_format_type_changed
        )
        self.p_audio_radio.pack(side='left', padx=(0, 20))
        
        self.p_quality_lbl = ttk.Label(p_format_row, text="Quality:", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        self.p_quality_lbl.pack(side='left', padx=(0, 10))
        
        self.p_quality_var = tk.StringVar(value="Best Quality")
        self.p_quality_combobox = ttk.Combobox(
            p_format_row, textvariable=self.p_quality_var, state='readonly', width=18, style='TCombobox'
        )
        self.p_quality_combobox['values'] = ("Best Quality", "1080p", "720p", "480p", "360p")
        self.p_quality_combobox.pack(side='left')

        # Playlist Download Panel (Progress bars - Initially hidden)
        self.playlist_download_panel = ttk.Frame(frame, style='Card.TFrame', padding=15)
        
        self.p_overall_lbl = ttk.Label(self.playlist_download_panel, text="Downloading video 0 of 0...", style='Title.Card.TLabel')
        self.p_overall_lbl.pack(anchor='w', pady=(0, 6))
        
        self.p_dl_status_lbl = ttk.Label(self.playlist_download_panel, text="Analyzing progress...", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.p_dl_status_lbl.pack(anchor='w', pady=(0, 10))
        
        self.p_progress_canvas = tk.Canvas(self.playlist_download_panel, bg=self.colors['progress_bg'], height=8, highlightthickness=0)
        self.p_progress_canvas.pack(fill='x', pady=(0, 8))
        self.p_progress_bar_rect = self.p_progress_canvas.create_rectangle(0, 0, 0, 8, fill=self.colors['accent'], width=0)
        
        p_stats_row = ttk.Frame(self.playlist_download_panel, style='Card.TFrame')
        p_stats_row.pack(fill='x')
        
        self.p_percent_lbl = ttk.Label(p_stats_row, text="0.0%", style='Card.TLabel', font=('Segoe UI', 10, 'bold'))
        self.p_percent_lbl.pack(side='left')
        
        self.p_speed_lbl = ttk.Label(p_stats_row, text="Speed: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.p_speed_lbl.pack(side='left', padx=30)
        
        self.p_eta_lbl = ttk.Label(p_stats_row, text="ETA: --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.p_eta_lbl.pack(side='left')
        
        self.p_size_lbl = ttk.Label(p_stats_row, text="-- / --", style='Card.TLabel', foreground=self.colors['text_muted'])
        self.p_size_lbl.pack(side='right')

        # Playlist Action row
        self.playlist_action_row = ttk.Frame(frame)
        self.playlist_action_row.pack(fill='x', pady=(10, 0))
        
        self.p_cancel_btn = ttk.Button(
            self.playlist_action_row, text="Cancel Batch", style='Secondary.TButton',
            command=self.cancel_active_download
        )
        
        self.playlist_download_btn = ttk.Button(
            self.playlist_action_row, text="Download Selected Videos", style='Accent.TButton',
            command=self.start_playlist_download
        )
        self.playlist_download_btn.pack(side='right')
        self.playlist_download_btn.configure(state='disabled')

    def on_playlist_format_type_changed(self):
        if self.p_format_type.get() == "audio":
            self.p_quality_lbl.configure(text="Audio Quality:")
            self.p_quality_combobox['values'] = ("Best (320kbps)", "Medium (192kbps)", "Low (128kbps)")
            self.p_quality_var.set("Medium (192kbps)")
        else:
            self.p_quality_lbl.configure(text="Quality / Resolution:")
            self.p_quality_combobox['values'] = ("Best Quality", "1080p", "720p", "480p", "360p")
            self.p_quality_var.set("Best Quality")

    def toggle_all_playlist_checkboxes(self, select_all):
        for var in self.playlist_checkbox_vars:
            var.set(select_all)

    def start_fetching_playlist(self):
        url = self.playlist_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a valid Playlist URL first!")
            return
            
        self.playlist_fetch_btn.configure(state='disabled')
        self.update_status("Retrieving playlist video list...", 'blue')
        
        self.playlist_placeholder.pack_forget()
        self.playlist_view_card.pack_forget()
        self.playlist_options_card.pack_forget()
        
        # Clear checklist variables
        self.playlist_checkbox_vars.clear()
        
        # Remove old widgets
        for widget in self.playlist_checkbox_widgets:
            widget.destroy()
        self.playlist_checkbox_widgets.clear()
        
        threading.Thread(target=self.fetch_playlist_worker, args=(url,), daemon=True).start()

    def fetch_playlist_worker(self, url):
        if not YT_DLP_AVAILABLE:
            self.root.after(0, self.on_playlist_fetch_failed, "yt-dlp missing.")
            return

        # Use extract_flat to fetch entries extremely fast without downloading them
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info.get('_type') != 'playlist':
                self.root.after(0, self.on_playlist_fetch_failed, "This URL is not a playlist (type is single video).")
            else:
                self.root.after(0, self.on_playlist_fetch_success, info)
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            self.root.after(0, self.on_playlist_fetch_failed, err_msg)

    def on_playlist_fetch_success(self, info):
        self.current_playlist_info = info
        self.playlist_fetch_btn.configure(state='normal')
        
        self.playlist_placeholder.pack_forget()
        self.playlist_view_card.pack(fill='both', expand=True, pady=(0, 10))
        self.playlist_options_card.pack(fill='x', pady=(0, 10))
        self.playlist_download_btn.configure(state='normal')
        
        self.playlist_title_lbl.configure(text=f"Playlist: {info.get('title', 'Unknown Playlist')}")
        entries = info.get('entries', [])
        self.playlist_count_lbl.configure(text=f"Videos Found: {len(entries)}")
        
        # Populate scrollable list of videos
        scroll_frame = self.playlist_scroll_frame.scrollable_frame
        
        for idx, entry in enumerate(entries):
            title = entry.get('title', 'Unknown Title')
            duration = format_duration(entry.get('duration'))
            uploader = entry.get('uploader') or entry.get('channel', 'Unknown Channel')
            
            # Checkbox variable
            chk_var = tk.BooleanVar(value=True)
            self.playlist_checkbox_vars.append(chk_var)
            
            # Item container
            item_row = ttk.Frame(scroll_frame, style='Card.TFrame', padding=5)
            item_row.pack(fill='x', pady=2, padx=5)
            self.playlist_checkbox_widgets.append(item_row)
            
            chk = tk.Checkbutton(
                item_row, variable=chk_var, bg=self.colors['card'], activebackground=self.colors['card'],
                selectcolor=self.colors['bg'], fg=self.colors['text'], activeforeground=self.colors['text']
            )
            chk.pack(side='left', padx=(5, 10))
            
            title_lbl = ttk.Label(item_row, text=f"{idx+1}. {title}", font=('Segoe UI', 9, 'bold'), style='Card.TLabel', wraplength=480, justify='left')
            title_lbl.pack(side='left', fill='x', expand=True)
            
            detail_lbl = ttk.Label(item_row, text=f"{uploader} | {duration}", font=('Segoe UI', 9), style='Card.TLabel', foreground=self.colors['text_muted'])
            detail_lbl.pack(side='right', padx=10)
            
        self.on_playlist_format_type_changed()
        self.update_status("Playlist parsed successfully!", 'green')

    def on_playlist_fetch_failed(self, error_message):
        self.playlist_fetch_btn.configure(state='normal')
        self.playlist_placeholder.pack(fill='both', expand=True)
        self.playlist_view_card.pack_forget()
        self.playlist_options_card.pack_forget()
        self.playlist_download_btn.configure(state='disabled')
        messagebox.showerror("Playlist Extraction Failed", f"Could not load playlist:\n\n{error_message}")
        self.update_status("Playlist load failed.", 'accent')

    def start_playlist_download(self):
        if not self.current_playlist_info or not self.playlist_checkbox_vars:
            return
            
        # Get checked entries
        entries = self.current_playlist_info.get('entries', [])
        checked_entries = []
        for idx, var in enumerate(self.playlist_checkbox_vars):
            if var.get():
                checked_entries.append(entries[idx])
                
        if not checked_entries:
            messagebox.showwarning("Warning", "Please select at least one video to download!")
            return
            
        save_path = self.output_dir.get()
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Invalid download directory: {e}")
                return
                
        self.cancel_download = False
        
        self.playlist_download_btn.pack_forget()
        self.p_cancel_btn.pack(side='right')
        
        self.playlist_view_card.pack_forget()
        self.playlist_options_card.pack_forget()
        self.playlist_download_panel.pack(fill='x', pady=(0, 20))
        
        self.playlist_url_entry.configure(state='disabled')
        self.playlist_fetch_btn.configure(state='disabled')
        
        # Reset progress components
        self.p_progress_canvas.coords(self.p_progress_bar_rect, 0, 0, 0, 8)
        self.p_percent_lbl.configure(text="0.0%")
        self.p_speed_lbl.configure(text="Speed: Starting...")
        self.p_eta_lbl.configure(text="ETA: Calculating...")
        self.p_size_lbl.configure(text="-- / --")
        
        self.update_status("Starting batch playlist downloads...", 'blue')
        
        self.download_thread = threading.Thread(
            target=self.playlist_download_worker,
            args=(checked_entries, save_path),
            daemon=True
        )
        self.download_thread.start()

    def playlist_download_worker(self, entries, save_path):
        audio_only = self.p_format_type.get() == "audio"
        quality = self.p_quality_var.get()
        total_items = len(entries)
        
        success_count = 0
        for index, entry in enumerate(entries, 1):
            if self.cancel_download:
                break
                
            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
            
            # Setup specific options
            ydl_opts = {
                'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.yt_dlp_playlist_progress_hook],
                'quiet': True,
                'no_warnings': True,
                'concurrent_fragment_downloads': 30,
                'http_chunk_size': 10485760,
            }
            
            # Apply advanced settings
            if self.embed_metadata.get() and FFMPEG_AVAILABLE:
                ydl_opts.setdefault('postprocessors', []).append({
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                })
            if self.embed_thumbnail.get() and FFMPEG_AVAILABLE:
                ydl_opts.setdefault('postprocessors', []).append({
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                })
            if self.save_thumbnail_file.get():
                ydl_opts['writethumbnail'] = True
            if self.download_subtitles.get():
                ydl_opts.update({
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en'],
                    'subtitlesformat': 'srt/vtt/best',
                })
            
            if audio_only:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192' if 'Medium' in quality else ('320' if 'Best' in quality else '128'),
                    }],
                })
            else:
                if quality == "Best Quality":
                    ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
                else:
                    height = quality.replace("p", "")
                    ydl_opts.update({
                        'format': f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
                    })
            
            # Update UI labels
            self.root.after(0, self.p_overall_lbl.configure, {"text": f"Downloading video {index} of {total_items}..."})
            self.root.after(0, self.p_dl_status_lbl.configure, {"text": f"Video: {entry.get('title', 'Unknown')}"})
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    
                # Save to history
                final_path = info.get('_filename')
                if 'requested_downloads' in info and info['requested_downloads']:
                    final_path = info['requested_downloads'][0].get('filepath', final_path)
                
                size_val = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0
                save_to_history(
                    info.get('title', entry.get('title')),
                    final_path or "Unknown Location",
                    'MP3 Audio' if audio_only else 'MP4 Video',
                    format_bytes(size_val)
                )
                success_count += 1
            except Exception as e:
                # If cancelled, break out
                if self.cancel_download or "DownloadCancelledException" in str(e):
                    break
                print(f"Failed to download playlist item: {e}")
                
        self.root.after(0, self.refresh_history_ui)
        if self.cancel_download:
            self.root.after(0, self.on_playlist_download_complete, False, "Batch download cancelled.")
        else:
            self.root.after(0, self.on_playlist_download_complete, True, f"Successfully downloaded {success_count} of {total_items} items.")

    def yt_dlp_playlist_progress_hook(self, d):
        if self.cancel_download:
            raise Exception("DownloadCancelledException")
            
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            percent = (downloaded / total) * 100 if total > 0 else 0
            
            progress_data = {
                'percent': percent,
                'downloaded': downloaded,
                'total': total,
                'speed': speed,
                'eta': eta,
                'filename': os.path.basename(d.get('filename', ''))
            }
            self.root.after(0, self.update_playlist_download_progress_ui, progress_data)
            
        elif d['status'] == 'finished':
            self.root.after(0, self.update_status, "Merging audio/video files...", 'blue')

    def update_playlist_download_progress_ui(self, data):
        if self.cancel_download:
            return
            
        percent = data['percent']
        speed = data['speed']
        eta = data['eta']
        downloaded = data['downloaded']
        total = data['total']
        
        canvas_width = self.p_progress_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 750
            
        bar_width = int(canvas_width * (percent / 100))
        self.p_progress_canvas.coords(self.p_progress_bar_rect, 0, 0, bar_width, 8)
        
        self.p_percent_lbl.configure(text=f"{percent:.1f}%")
        self.p_speed_lbl.configure(text=f"Speed: {format_bytes(speed)}/s" if speed else "Speed: --")
        self.p_eta_lbl.configure(text=f"ETA: {format_duration(eta)}" if eta else "ETA: --")
        self.p_size_lbl.configure(text=f"{format_bytes(downloaded)} / {format_bytes(total)}")
        self.update_status(f"Downloading playlist item: {data['filename'][:40]}...", 'blue')

    def on_playlist_download_complete(self, success, message):
        self.p_cancel_btn.pack_forget()
        self.playlist_download_btn.pack(side='right')
        self.playlist_download_panel.pack_forget()
        
        self.playlist_view_card.pack(fill='both', expand=True, pady=(0, 10))
        self.playlist_options_card.pack(fill='x', pady=(0, 10))
        
        self.playlist_url_entry.configure(state='normal')
        self.playlist_fetch_btn.configure(state='normal')
        
        if success:
            self.update_status("Batch completed!", 'green')
            messagebox.showinfo("Success", message + "\n\nFiles saved in:\n" + self.output_dir.get())
        else:
            self.update_status("Batch cancelled.", 'accent')
            messagebox.showinfo("Batch Status", message)

    # ==============================================================================
    # TAB 3: YOUTUBE SEARCH
    # ==============================================================================
    def build_search_tab_ui(self):
        frame = self.tab_frames["search"]
        
        # Search Entry Bar
        search_bar_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        search_bar_card.pack(fill='x', pady=(0, 15))
        
        search_lbl = ttk.Label(search_bar_card, text="Search YouTube Videos Directly", style='Title.Card.TLabel')
        search_lbl.pack(anchor='w', pady=(0, 8))
        
        search_row = ttk.Frame(search_bar_card, style='Card.TFrame')
        search_row.pack(fill='x')
        
        self.search_entry = tk.Entry(
            search_row,
            bg='#2C2C2C',
            fg='#FFFFFF',
            insertbackground='#FFFFFF',
            relief='flat',
            font=('Segoe UI', 11),
            bd=8
        )
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.search_entry.bind('<Return>', lambda e: self.trigger_search())
        
        self.search_btn = ttk.Button(
            search_row,
            text="Search",
            style='Accent.TButton',
            command=self.trigger_search
        )
        self.search_btn.pack(side='right')

        # Results Display Card
        self.search_results_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        self.search_results_card.pack(fill='both', expand=True)
        
        self.search_placeholder = ttk.Label(
            self.search_results_card,
            text="Search keywords to list matching YouTube videos.",
            font=('Segoe UI', 11),
            foreground=self.colors['text_muted'],
            justify='center',
            style='Card.TLabel'
        )
        self.search_placeholder.pack(expand=True)
        
        # Scrollable container for search result items
        self.search_scroll_frame = ScrollableFrame(self.search_results_card, self.colors)

    def trigger_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
            
        self.search_btn.configure(state='disabled')
        self.update_status(f"Searching YouTube for '{query}'...", 'blue')
        
        # Clear previous search image references from memory
        self.search_thumbnail_images.clear()
        
        # Remove old widgets inside scroll container
        for widget in self.search_scroll_frame.scrollable_frame.winfo_children():
            widget.destroy()
            
        self.search_placeholder.pack_forget()
        self.search_scroll_frame.pack_forget()
        
        # Draw search progress loader
        self.search_loader_lbl = ttk.Label(self.search_results_card, text="Fetching search matches from YouTube...", font=('Segoe UI', 10, 'italic'), style='Card.TLabel')
        self.search_loader_lbl.pack(expand=True)
        
        threading.Thread(target=self.run_search_worker, args=(query,), daemon=True).start()

    def run_search_worker(self, query):
        if not YT_DLP_AVAILABLE:
            self.root.after(0, self.on_search_failed, "yt-dlp package is missing.")
            return

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Fetch 5 matching entries
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            
            self.root.after(0, self.on_search_success, info.get('entries', []))
        except Exception as e:
            self.root.after(0, self.on_search_failed, str(e))

    def on_search_success(self, entries):
        self.search_btn.configure(state='normal')
        if hasattr(self, 'search_loader_lbl') and self.search_loader_lbl.winfo_exists():
            self.search_loader_lbl.destroy()
            
        if not entries:
            self.search_placeholder.configure(text="No videos found. Try a different query.")
            self.search_placeholder.pack(expand=True)
            self.update_status("No results found.", 'accent')
            return
            
        self.search_scroll_frame.pack(fill='both', expand=True)
        self.update_status(f"Found {len(entries)} matching videos.", 'green')
        
        scroll_container = self.search_scroll_frame.scrollable_frame
        
        for idx, entry in enumerate(entries):
            vid_id = entry.get('id')
            title = entry.get('title', 'Unknown Title')
            channel = entry.get('uploader') or entry.get('channel', 'Unknown Channel')
            duration = format_duration(entry.get('duration'))
            views = f"{entry.get('view_count', 0):,}" if entry.get('view_count') else "N/A"
            thumbnail_url = entry.get('thumbnail')
            
            # Card for this result
            result_card = ttk.Frame(scroll_container, style='Card.TFrame', padding=10)
            result_card.pack(fill='x', pady=5, padx=5)
            
            # Canvas for result thumbnail
            t_canvas = tk.Canvas(result_card, bg='#181818', highlightthickness=1, highlightbackground=self.colors['border'], width=120, height=68)
            t_canvas.pack(side='left', padx=(0, 12))
            
            # Draw canvas thumbnail placeholder
            t_canvas.create_rectangle(0, 0, 120, 68, fill='#1A1A1A', outline=self.colors['border'])
            t_canvas.create_polygon(0, 0, 15, 0, 0, 15, fill=self.colors['accent'])
            t_canvas.create_text(60, 34, text="Loading...", fill=self.colors['text_muted'], font=('Segoe UI', 8))
            
            # Start background load for search thumbnail
            if thumbnail_url:
                threading.Thread(target=self.load_search_thumbnail, args=(thumbnail_url, t_canvas), daemon=True).start()
                
            # Details block
            details_f = ttk.Frame(result_card, style='Card.TFrame')
            details_f.pack(side='left', fill='both', expand=True)
            
            v_title_lbl = ttk.Label(details_f, text=title, font=('Segoe UI', 10, 'bold'), style='Card.TLabel', wraplength=480, justify='left')
            v_title_lbl.pack(anchor='w', pady=(0, 4))
            
            v_meta_lbl = ttk.Label(details_f, text=f"Channel: {channel}  |  Duration: {duration}  |  Views: {views}", font=('Segoe UI', 9), style='Card.TLabel', foreground=self.colors['text_muted'])
            v_meta_lbl.pack(anchor='w')
            
            # Action button to load video
            load_url = f"https://www.youtube.com/watch?v={vid_id}"
            btn = ttk.Button(
                result_card, 
                text="Load Video", 
                style='Accent.TButton',
                command=lambda url=load_url: self.load_video_to_downloader(url)
            )
            btn.pack(side='right', padx=10, pady=10)

    def load_search_thumbnail(self, url, canvas):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                image_data = response.read()

            if PILLOW_AVAILABLE:
                import io
                image = Image.open(io.BytesIO(image_data))
                image = image.resize((120, 68), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(image)
                # Keep reference to prevent GC
                self.search_thumbnail_images.append(photo)
                
                def update_canvas():
                    if canvas.winfo_exists():
                        canvas.delete("all")
                        canvas.create_image(60, 34, image=photo)
                        canvas.create_polygon(0, 0, 12, 0, 0, 12, fill=self.colors['accent'])
                self.root.after(0, update_canvas)
        except Exception:
            pass

    def load_video_to_downloader(self, url):
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, url)
        self.show_tab("single")
        self.start_fetching_metadata()

    def on_search_failed(self, error_message):
        self.search_btn.configure(state='normal')
        if hasattr(self, 'search_loader_lbl') and self.search_loader_lbl.winfo_exists():
            self.search_loader_lbl.destroy()
            
        self.search_placeholder.configure(text="Search failed. Check your network.")
        self.search_placeholder.pack(expand=True)
        messagebox.showerror("Search Failed", f"An error occurred during YouTube search:\n\n{error_message}")
        self.update_status("Search failed.", 'accent')

    # ==============================================================================
    # TAB 4: LIBRARY HISTORY
    # ==============================================================================
    def build_history_tab_ui(self):
        frame = self.tab_frames["history"]
        
        # Header title
        title_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        title_card.pack(fill='x', pady=(0, 15))
        
        lbl = ttk.Label(title_card, text="Completed Downloads Library", style='Title.Card.TLabel')
        lbl.pack(side='left')
        
        clear_btn = ttk.Button(
            title_card, text="Clear List", style='Secondary.TButton', padding=(8, 4),
            command=self.clear_all_history
        )
        clear_btn.pack(side='right')

        # Scrollable container for history items
        self.history_results_card = ttk.Frame(frame, style='Card.TFrame', padding=15)
        self.history_results_card.pack(fill='both', expand=True)
        
        self.history_placeholder = ttk.Label(
            self.history_results_card,
            text="No download history found. Completed downloads will appear here.",
            font=('Segoe UI', 11),
            foreground=self.colors['text_muted'],
            justify='center',
            style='Card.TLabel'
        )
        self.history_placeholder.pack(expand=True)
        
        self.history_scroll_frame = ScrollableFrame(self.history_results_card, self.colors)

    def refresh_history_ui(self):
        history = load_history()
        
        # Clear scroll container widgets
        for widget in self.history_scroll_frame.scrollable_frame.winfo_children():
            widget.destroy()
            
        self.history_placeholder.pack_forget()
        self.history_scroll_frame.pack_forget()
        
        if not history:
            self.history_placeholder.pack(expand=True)
            return
            
        self.history_scroll_frame.pack(fill='both', expand=True)
        scroll_container = self.history_scroll_frame.scrollable_frame
        
        for idx, entry in enumerate(history):
            title = entry.get('title', 'Unknown Title')
            file_path = entry.get('path', '')
            format_type = entry.get('format', 'MP4 Video')
            size = entry.get('size', '--')
            timestamp = entry.get('timestamp', '--')
            
            card = ttk.Frame(scroll_container, style='Card.TFrame', padding=10)
            card.pack(fill='x', pady=4, padx=5)
            
            # Format visual indicator
            if "Audio" in format_type:
                icon_lbl = tk.Label(card, text="AUDIO", bg='#2979FF', fg='#FFFFFF', font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
            else:
                icon_lbl = tk.Label(card, text="VIDEO", bg='#FF3E3E', fg='#FFFFFF', font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
            icon_lbl.pack(side='left', padx=(5, 12))
            
            # Detail section
            info_f = ttk.Frame(card, style='Card.TFrame')
            info_f.pack(side='left', fill='both', expand=True)
            
            title_lbl = ttk.Label(info_f, text=title, font=('Segoe UI', 10, 'bold'), style='Card.TLabel', wraplength=480, justify='left')
            title_lbl.pack(anchor='w', pady=(0, 4))
            
            meta_lbl = ttk.Label(
                info_f, 
                text=f"Format: {format_type}  |  Size: {size}  |  Downloaded: {timestamp}",
                font=('Segoe UI', 9), style='Card.TLabel', foreground=self.colors['text_muted']
            )
            meta_lbl.pack(anchor='w')
            
            # Buttons row
            btn_f = ttk.Frame(card, style='Card.TFrame')
            btn_f.pack(side='right', padx=5)
            
            # "Play" Button
            play_btn = ttk.Button(
                btn_f, text="Play File", style='Accent.TButton', padding=(8, 4),
                command=lambda path=file_path: self.play_downloaded_file(path)
            )
            play_btn.pack(side='left', padx=5)
            if not os.path.exists(file_path):
                play_btn.configure(state='disabled', text="Missing")
            
            # "Open Folder" Button
            folder_btn = ttk.Button(
                btn_f, text="Folder", style='Secondary.TButton', padding=(8, 4),
                command=lambda path=file_path: self.open_containing_folder(path)
            )
            folder_btn.pack(side='left', padx=5)
            if not os.path.exists(file_path):
                folder_btn.configure(state='disabled')
                
            # "Remove" Button
            remove_btn = ttk.Button(
                btn_f, text="Remove", style='Secondary.TButton', padding=(4, 4),
                command=lambda idx=idx: self.remove_history_item(idx)
            )
            remove_btn.pack(side='left', padx=5)

    def play_downloaded_file(self, file_path):
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File does not exist or has been deleted/moved.")
            return
            
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to play file:\n\n{e}")

    def open_containing_folder(self, file_path):
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File folder does not exist.")
            return
            
        try:
            abs_path = os.path.normpath(file_path)
            if os.name == 'nt':
                # Open explorer and select the specific file
                subprocess.run(['explorer', '/select,', abs_path])
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', abs_path])
            else:
                dir_path = os.path.dirname(abs_path)
                subprocess.run(['xdg-open', dir_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n\n{e}")

    def remove_history_item(self, idx):
        history = load_history()
        if 0 <= idx < len(history):
            history.pop(idx)
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=4, ensure_ascii=False)
            except Exception:
                pass
            self.refresh_history_ui()

    def clear_all_history(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to clear your download library history? This won't delete the physical files."):
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception:
                pass
            self.refresh_history_ui()


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    # Check for command line arguments (run in CLI Mode if argument exists)
    if len(sys.argv) > 1:
        # Simple CLI parser
        args = sys.argv[1:]
        url = None
        audio_only = False
        quality = 'best'
        output_dir = None
        
        # Iterate and capture arguments
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
                url = arg
            i += 1
            
        if url:
            cli = DownloaderCLI(url, output_dir, audio_only, quality)
            success = cli.run()
            sys.exit(0 if success else 1)
        else:
            print("Usage Examples:")
            print("  python downloader.py <YouTube_URL>                   (Downloads best quality video)")
            print("  python downloader.py <YouTube_URL> -a                (Downloads high-quality MP3 audio)")
            print("  python downloader.py <YouTube_URL> -q 720            (Downloads maximum 720p resolution video)")
            print("  python downloader.py <YouTube_URL> -o \"C:\\path\\\"    (Specifies output destination)")
            print("  python downloader.py \"search query\"                 (Searches YouTube and downloads top result)")
            print("\nOr run without arguments to launch the modern graphical desktop interface!")
            sys.exit(1)
            
    else:
        root = tk.Tk()
        app = DownloaderGUI(root)
        root.mainloop()
