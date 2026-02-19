import yt_dlp
import os
import sys
import certifi
import ssl
import shutil
import argparse

# Fix SSL: CERTIFICATE_VERIFY_FAILED error in PyInstaller builds
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

def check_ffmpeg() -> bool:
    """
    Checks if ffmpeg is installed and available in the system PATH.
    """
    if shutil.which("ffmpeg") is None:
        return False
    return True

def validate_url(url: str) -> bool:
    """
    Validates if the provided string is a plausible YouTube URL.
    Checks for common YouTube domains and video/playlist patterns.
    """
    if "youtube.com" in url or "youtu.be" in url:
        return True
    return False

# Global variable to store total playlist items for progress reporting
playlist_total_items = 0

def progress_hook(d):
    """
    Callback function to display download progress.
    Handles both single video and playlist progress formats.
    """
    if d['status'] == 'downloading':
        try:
            # Extract basic progress info
            percent = d.get('_percent_str', '').replace('%','')
            eta = d.get('_eta_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            
            # Playlist specific info
            playlist_index = d.get('playlist_index')
            n_entries = d.get('n_entries') or playlist_total_items
            
            if playlist_index and n_entries:
                # Playlist format: "Downloading 1/120 1%"
                print(f"\rDownloading {playlist_index}/{n_entries} {percent}% | ETA: {eta} | Speed: {speed}", end='', flush=True)
            else:
                # Single video format
                print(f"\rDownloading: {percent}% | ETA: {eta} | Speed: {speed}", end='', flush=True)
                
        except Exception:
            pass
    elif d['status'] == 'finished':
        print("\nDownload complete. Processing...", flush=True)

def normalize_metadata(info, incomplete=False):
    """
    Match filter function to normalize artist and track metadata.
    This runs BEFORE the download starts.
    Modifies the info dictionary in-place.
    """
    # 1. Artist Normalization
    raw_artist = info.get('artist')
    if not raw_artist:
        raw_artist = info.get('uploader')
    
    final_artist_list = []
    
    if raw_artist:
        # Handle if it's already a list (some extractors do this) or a comma-separated string
        if isinstance(raw_artist, str):
            parts = raw_artist.split(',')
        elif isinstance(raw_artist, list):
            parts = raw_artist
        else:
            parts = [str(raw_artist)]

        # Clean, Deduplicate (preserve order), Limit to 3
        seen = set()
        for p in parts:
            clean_p = str(p).strip()
            if clean_p and clean_p.lower() not in seen:
                final_artist_list.append(clean_p)
                seen.add(clean_p.lower())
        
        final_artist_list = final_artist_list[:3]
    
    if not final_artist_list:
        final_artist = "Unknown Artist"
    else:
        final_artist = " & ".join(final_artist_list)
    
    # Update info dict with cleaned artist
    info['artist'] = final_artist
    
    # 2. Track Normalization
    # Fallback to title if track is missing
    current_track = info.get('track')
    if not current_track:
        current_track = info.get('title', 'Unknown Track')
    
    # Duplicate Artist Prevention Logic
    # Check if the track/title already starts with the artist name
    # Case-insensitive check
    
    if final_artist and final_artist != "Unknown Artist":
        # Create normalized versions for comparison
        norm_artist = final_artist.lower()
        norm_track = str(current_track).lower()
        
        if norm_track.startswith(norm_artist):
            # Remove the artist part
            # We use the length of the artist string to slice the track string
            # This preserves the original casing of the remaining track title
            cleaned_track = current_track[len(final_artist):]
            
            # Remove leading separators (e.g. " - ", " : ", etc)
            # We strip common separators and whitespace
            cleaned_track = cleaned_track.lstrip(" -:|")
            
            # If the result is not empty, use it. Otherwise keep original (edge case where track == artist)
            if cleaned_track.strip():
                current_track = cleaned_track

    info['track'] = current_track
        
    return None # Return None to let the download proceed

def get_playlist_info(url: str):
    """
    Extracts playlist information to count total videos.
    Returns the total count of videos if it's a playlist, else None.
    """
    ydl_opts = {
        'extract_flat': 'in_playlist', # Just extract video IDs, don't download
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                return len(list(info['entries']))
    except Exception:
        pass
    return None

def download_audio(url: str, output_dir: str | None = None) -> list[str]:
    """
    Downloads audio from the provided YouTube URL or Playlist.
    Converts to MP3 using ffmpeg with metadata-based filenames.
    Returns a list of absolute paths to the downloaded files.
    """
    global playlist_total_items
    
    if output_dir:
        download_path = output_dir
    else:
        download_path = os.path.join(os.getcwd(), 'downloads')
    
    # Create downloads folder if it doesn't exist
    if not os.path.exists(download_path):
        try:
            os.makedirs(download_path)
            print(f"Created directory: {download_path}")
        except OSError as e:
            print(f"Error creating directory: {e}")
            return []

    # Check if it's a playlist to get total count
    print("Checking URL...", end='', flush=True)
    count = get_playlist_info(url)
    if count and count > 1:
        print(f"\r{count} songs found in this playlist.")
        playlist_total_items = count
    else:
        print("\rSingle video detected.      ") # clear line
        playlist_total_items = 0

    # Output template: Artist - Track.mp3
    # We rely on normalize_metadata to populate 'artist' and 'track'
    out_tmpl = os.path.join(download_path, '%(artist)s - %(track)s.%(ext)s')
    
    downloaded_files = []

    def postprocessor_hook(d):
        if d['status'] == 'finished':
            downloaded_files.append(d['filename'])

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }, {
             'key': 'FFmpegMetadata',
             # This injects the metadata into the file
        }],
        'outtmpl': out_tmpl,
        'progress_hooks': [progress_hook, postprocessor_hook],
        'match_filter': normalize_metadata, # Call our normalization function
        'ignoreerrors': True,
        'quiet': True,
        'no_warnings': True,
        'writethumbnail': False, 
    }

    print(f"Starting download...")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])
            
        if error_code:
             print(f"\nDownload finished with some errors (Code: {error_code}).")
        else:
             print(f"\nAll operations completed successfully.")
        
        # The hook captures the filename BEFORE FFmpeg conversion (e.g. .webm or .m4a)
        # We need to return the .mp3 filenames.
        mp3_files = []
        for f in downloaded_files:
            base, _ = os.path.splitext(f)
            mp3_path = base + ".mp3"
            if os.path.exists(mp3_path):
                mp3_files.append(mp3_path)
        
        return mp3_files

    except Exception as e:
        print(f"\nA critical error occurred: {e}")
        return []

def get_video_info(url: str) -> list[dict]:
    """
    Extracts metadata for a video or playlist without downloading.
    Returns a list of dictionaries containing 'artist' and 'title'.
    """
    # Options for simulation
    ydl_opts_sim = {
        'quiet': True,
        'simulate': True,
        'extract_flat': 'in_playlist', # Try to get playlist entries fast
        'no_warnings': True,
        'cookiefile': 'cookies.txt', # Use cookies if available
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts_sim) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return []

            if 'entries' in info:
                # Playlist
                try:
                    entries = list(info['entries'])
                except TypeError:
                    entries = []

                for entry in entries:
                    # Let's try to construct a minimal info dict for normalization
                    temp_info = entry.copy()
                    
                    # Run normalization
                    normalize_metadata(temp_info)
                    
                    track_title = temp_info.get('track')
                    if not track_title:
                        track_title = temp_info.get('title', 'Unknown Title')
                        
                    artist_name = temp_info.get('artist')
                    if not artist_name:
                        artist_name = temp_info.get('uploader', 'Unknown Artist')
                    
                    results.append({
                        'artist': artist_name,
                        'title': track_title,
                        'is_playlist': True,
                        'playlist_title': info.get('title', 'Unknown Playlist'),
                        'original_url': url
                    })

            else:
                # Single Video
                normalize_metadata(info)
                
                track_title = info.get('track')
                if not track_title:
                    track_title = info.get('title', 'Unknown Title')
                    
                artist_name = info.get('artist')
                if not artist_name:
                    artist_name = info.get('uploader', 'Unknown Artist')
                
                results.append({
                    'artist': artist_name,
                    'title': track_title,
                    'is_playlist': False,
                    'original_url': url
                })
        
        return results

    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return []

def show_info(url: str):
    """
    Extracts and displays metadata for a video or playlist without downloading.
    """
    print(f"Fetching metadata for: {url}")
    
    data = get_video_info(url)
    
    if not data:
        print("Error: Could not extract information.")
        return

    if data[0].get('is_playlist'):
         print(f"\nPlaylist: {data[0].get('playlist_title')}")
         print(f"Found {len(data)} entries:\n")
         
         for i, item in enumerate(data, 1):
             print(f"{i}. {item['artist']} - {item['title']}")
    else:
         print(f"\n{data[0]['artist']} - {data[0]['title']}")

def main():
    if not check_ffmpeg():
        print("\nCRITICAL ERROR: ffmpeg is not installed or not found in PATH.")
        print("This program requires ffmpeg to convert audio to MP3.")
        print("\nPlease install ffmpeg:")
        print("  - Windows: Download from https://ffmpeg.org/download.html and add to PATH.")
        print("  - Ubuntu/Debian: sudo apt install ffmpeg")
        print("  - macOS: brew install ffmpeg")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="YouTube Audio Downloader & Converter")
    parser.add_argument("url", nargs="?", help="YouTube URL (Video or Playlist)")
    parser.add_argument("--show", action="store_true", help="Show metadata (Artist - Title) without downloading")
    
    args = parser.parse_args()
    
    url = args.url
    
    # If no URL provided via args, prompt recursively? Or just once?
    # Original behavior was: prompt if no args.
    if not url:
        print("--- Python YouTube Audio Downloader ---")
        while True:
            url_input = input("Enter YouTube Song or Playlist here: ").strip()
            if url_input:
                url = url_input
                break
            print("Error: Input cannot be empty.")
    
    if not validate_url(url):
         print("Error: Invalid YouTube URL provided. Please check the link and try again.")
         sys.exit(1)

    if args.show:
        show_info(url)
    else:
        # Proceed with download
        download_audio(url)

if __name__ == "__main__":
    main()
