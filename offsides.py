import discord 
import os
import aiohttp
import yt_dlp
from discord.ext import commands, tasks
from deep_translator import GoogleTranslator

# Configuración global
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = -1002462623914  # ID del chat de Telegram
DISCORD_CHANNEL_ID = 1180556157161590864  # ID del canal de Discord

# Intents de Discord
intents = discord.Intents.default()
intents.message_content = True

# Bot de Discord
bot = commands.Bot(command_prefix="!", intents=intents)

# Variables globales
last_update_id = None

# Traductor de texto
translator = GoogleTranslator(source='auto', target='es')

# Función para obtener mensajes de Telegram
async def fetch_telegram_messages():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if last_update_id is not None:
        params["offset"] = last_update_id + 1

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if "result" in data:
                    for update in data["result"]:
                        last_update_id = update["update_id"]
                        if "message" in update:
                            message = update["message"]
                            text = message.get("text", "") or message.get("caption", "")
                            media = None

                            if "photo" in message:
                                photo = message["photo"][-1]
                                media = {"type": "photo", "file_id": photo["file_id"]}
                            elif "video" in message:
                                video = message["video"]
                                media = {"type": "video", "file_id": video["file_id"]}

                            yield text, media
    except Exception as e:
        print(f"Error en fetch_telegram_messages: {str(e)}")

# Función para descargar video con yt_dlp
def download_video(url, filename):
    ydl_opts = {
        'outtmpl': filename,
        'format': 'mp4/best'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"Error al descargar video: {str(e)}")
        return False

# Loop asincrónico para verificar continuamente los mensajes de Telegram
@tasks.loop(seconds=10)
async def check_telegram():
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            print(f"No se pudo encontrar el canal de Discord con ID {DISCORD_CHANNEL_ID}")
            return

        async for text, media in fetch_telegram_messages():
            print(f"Mensaje recibido: {text}")

            translated_text = ""
            if text:
                try:
                    translated_text = translator.translate(text)
                except Exception as e:
                    print(f"Error en la traducción: {str(e)}")
                    translated_text = text

            embed = discord.Embed(title="Nuevo mensaje de OFFSIDES ⚽", description=translated_text, color=discord.Color.blue())
            if media:
                file_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={media['file_id']}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as response:
                        file_info = await response.json()
                        file_path = file_info["result"]["file_path"]
                        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

                        if media["type"] == "photo":
                            embed.set_image(url=download_url)
                            await channel.send(embed=embed)
                        elif media["type"] == "video":
                            video_filename = "telegram_video.mp4"
                            if download_video(download_url, video_filename):
                                await channel.send(embed=embed)
                                await channel.send(file=discord.File(video_filename))
                                os.remove(video_filename)
    except Exception as e:
        print(f"Error en check_telegram: {str(e)}")

# Evento de inicio del bot de Discord
@bot.event
async def on_ready():
    print(f"Bot de Discord conectado como {bot.user.name}")
    check_telegram.start()

# Ejecutar el bot de Discord
if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
