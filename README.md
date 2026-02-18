# Python YouTube Downloader

A high-performance, production-ready CLI application to download audio from YouTube videos and playlists, converting them to high-quality MP3s with normalized metadata.

## Features

- **Smart Metadata Normalization**: automatically cleans artist names, removes duplicates (e.g., "A, B, A" -> "A & B"), and strips redundant artist names from track titles.
- **Playlist Support**: 
    - Auto-detects playlists.
    - Displays "X songs found".
    - detailed progress reporting (e.g., "Downloading 1/120").
- **MP3 Conversion**: Uncompromised audio quality using `ffmpeg`.
- **Robust Error Handling**: Skips unavailable videos in playlists and resumes operation.
- **Cross-Platform**: Runs on Linux, Windows, and macOS (requires Python & FFmpeg).

## Requirements

- **Python 3.10+**
- **FFmpeg**: Must be installed and available in your system's PATH. This is required for audio conversion.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/youtube-downloader.git
    cd youtube-downloader
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

**Interactive Mode**:
Run the script without arguments and paste your URL when prompted.
```bash
python3 main.py
```

**Command Line Mode**:
Pass the URL directly as an argument.
```bash
python3 main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The audio files will be saved in the `downloads/` directory.

## Deployment / Building

You can build a standalone executable using `PyInstaller`:

```bash
pyinstaller --onefile --name "youtube-downloader" main.py
```

The executable will be located in the `dist/` folder.
**Note**: The standalone executable still requires `ffmpeg` to be installed on the target machine.

## Automatic Releases

This repository includes a GitHub Action workflow. Pushing a tag (e.g., `v1.0.0`) will automatically build and release the executable for both Ubuntu and Windows.
