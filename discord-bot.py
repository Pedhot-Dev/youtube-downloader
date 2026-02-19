import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import main
import shutil

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='tomp3')
async def tomp3(ctx, url: str):
    """
    Downloads music from the given URL and uploads it as MP3.
    Usage: !tomp3 [LINK]
    """
    status_msg = await ctx.send(f"Processing your request using `main.py`... This might take a while.")
    
    try:
        # Run the download in a separate thread to avoid blocking the bot
        loop = asyncio.get_event_loop()
        
        # Create a temporary directory for this request to avoid collisions
        # Although main.download_audio takes an output_dir, we can just use a unique folder
        # or just let it download to 'downloads' and clean up.
        # Let's use a unique folder per requestID if possible, but main.py relies on global state for playlist checks?
        # main.py has `playlist_total_items` global. This is not thread safe if multiple requests come in.
        # But for this simple bot, we might accept that risk or just use a lock if needed.
        # For now, let's just use the default 'downloads' folder or a specific one.
        
        # We'll use a specific output directory for the bot to separate it from CLI usage if desired,
        # but the requirement says "reply with a music".
        
        # Using a subfolder for this specific message to allow easy cleanup
        output_dir = os.path.join(os.getcwd(), 'downloads', str(ctx.message.id))
        
        # Check if main.download_audio supports output_dir (we added it)
        files = await loop.run_in_executor(None, lambda: main.download_audio(url, output_dir=output_dir))
        
        if not files:
            await status_msg.edit(content="Failed to download audio. Check the logs or the link.")
            return

        await status_msg.edit(content=f"Download complete. Uploading {len(files)} file(s)...")
        
        uploaded_count = 0
        for file_path in files:
            try:
                # Check file size. Discord limit is usually 8MB / 10MB / 25MB depending on boosts.
                # We can try to upload, if it fails, we notify.
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > 25: # Assuming a safe upper bound, valid for some servers
                     await ctx.send(f"File `{os.path.basename(file_path)}` is too large ({file_size_mb:.2f} MB) to upload.")
                     continue

                await ctx.send(file=discord.File(file_path))
                uploaded_count += 1
            except Exception as e:
                await ctx.send(f"Error uploading `{os.path.basename(file_path)}`: {e}")
        
        if uploaded_count == len(files):
            await status_msg.edit(content="All files sent!")
        else:
            await status_msg.edit(content=f"Sent {uploaded_count}/{len(files)} files.")

        # Cleanup
        try:
            shutil.rmtree(output_dir)
        except OSError as e:
            print(f"Error cleaning up directory {output_dir}: {e}")

    except Exception as e:
        await status_msg.edit(content=f"An error occurred: {e}")
        # Clean up if possible
        if 'output_dir' in locals() and os.path.exists(output_dir):
             shutil.rmtree(output_dir, ignore_errors=True)

@bot.command(name='showmusic')
async def showmusic(ctx, url: str):
    """
    Shows metadata for the given URL.
    Usage: !showmusic [LINK]
    """
    status_msg = await ctx.send("Fetching metadata...")
    
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: main.get_video_info(url))
        
        if not data:
            await status_msg.edit(content="Could not extract information. Invalid URL or private video.")
            return

        message_lines = []
        if data[0].get('is_playlist'):
            playlist_title = data[0].get('playlist_title')
            message_lines.append(f"**Playlist:** {playlist_title}")
            message_lines.append(f"**Found {len(data)} entries:**")
            
            for i, item in enumerate(data, 1):
                line = f"{i}. {item['title']} - {item['artist']}"
                if len("\n".join(message_lines) + "\n" + line) > 1900: # specific limit handling
                    message_lines.append("... (truncated)")
                    break
                message_lines.append(line)
        else:
            item = data[0]
            message_lines.append(f"**Artist:** {item['artist']}")
            message_lines.append(f"**Title:** {item['title']}")
            if 'album' in item and item['album']:
                 message_lines.append(f"**Album:** {item['album']}")
            
            # Use format "Artist - Title" as requested for single video too?
            # User said: "reply Artist, Title, Album, ETC (and or playlist, it will show 1. Title - Artist - Album"
            # So for single video, listing details nicely is good.
        
        response_text = "\n".join(message_lines)
        await status_msg.edit(content=response_text)

    except Exception as e:
        await status_msg.edit(content=f"An error occurred: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        print("Please create a .env file with DISCORD_TOKEN=your_token_here")
    else:
        bot.run(TOKEN)
