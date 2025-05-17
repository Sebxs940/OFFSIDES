import discord 
import os
import aiohttp
import yt_dlp
from discord.ext import commands, tasks
from deep_translator import GoogleTranslator
import logging
import json

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('telegram_discord_bot')

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
    
    # Primero, eliminar cualquier webhook existente
    delete_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    try:
        async with aiohttp.ClientSession() as session:
            await session.get(delete_webhook_url)
    except Exception as e:
        logger.error(f"Error al eliminar webhook: {str(e)}")

    params = {
        "timeout": 10,
        "allowed_updates": json.dumps(["message"])
    }
    if last_update_id is not None:
        params["offset"] = last_update_id + 1

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if not data.get("ok", False):
                    error_msg = data.get("description", "Error desconocido")
                    logger.error(f"Error en la API de Telegram: {error_msg}")
                    await asyncio.sleep(5)  # Esperar antes de reintentar
                    return
                
                if "result" not in data:
                    logger.warning("La respuesta de Telegram no contiene 'result'")
                    return
                    
                updates = data["result"]
                for update in updates:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        message = update["message"]
                        
                        # Extraer texto del mensaje (puede estar en diferentes campos)
                        text = ""
                        if "text" in message:
                            text = message["text"]
                        elif "caption" in message:
                            text = message["caption"]
                        
                        # Identificar tipo de media
                        media = None
                        if "photo" in message:
                            largest_photo = message["photo"][-1]  # Usar la foto de mayor calidad
                            media = {"type": "photo", "file_id": largest_photo["file_id"]}
                        elif "video" in message:
                            video = message["video"]
                            media = {"type": "video", "file_id": video["file_id"]}
                            
                        yield text, media
    except aiohttp.ClientError as ce:
        logger.error(f"Error de conexión con la API de Telegram: {str(ce)}")
    except KeyError as ke:
        logger.error(f"Error de clave en la respuesta de Telegram: {str(ke)}")
    except Exception as e:
        logger.error(f"Error inesperado en fetch_telegram_messages: {str(e)}")

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
        logger.error(f"Error al descargar video: {str(e)}")
        return False

# Loop asincrónico para verificar continuamente los mensajes de Telegram
@tasks.loop(seconds=30)  # Aumentar el intervalo a 30 segundos
async def check_telegram():
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            logger.error(f"No se pudo encontrar el canal de Discord con ID {DISCORD_CHANNEL_ID}")
            return

        async for text, media in fetch_telegram_messages():
            logger.info(f"Mensaje recibido: {text}")

            # Traducir el texto si existe
            translated_text = ""
            if text and text.strip():
                try:
                    translated_text = translator.translate(text)
                    logger.info(f"Texto traducido: {translated_text}")
                except Exception as e:
                    logger.error(f"Error en la traducción: {str(e)}")
                    translated_text = text  # Usar texto original si falla la traducción

            # Crear embed para el mensaje
            embed = discord.Embed(
                title="Nuevo mensaje de OFFSIDES ⚽", 
                description=translated_text, 
                color=discord.Color.blue()
            )
            
            # Manejar archivos multimedia
            if media:
                try:
                    file_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={media['file_id']}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as response:
                            response_data = await response.json()
                            
                            if not response_data.get("ok", False):
                                logger.error(f"Error al obtener información del archivo: {response_data.get('description', 'Error desconocido')}")
                                await channel.send(embed=embed)  # Enviar solo el embed sin media
                                continue
                                
                            if "result" not in response_data or "file_path" not in response_data["result"]:
                                logger.error("Respuesta de getFile no contiene la ruta del archivo")
                                await channel.send(embed=embed)  # Enviar solo el embed sin media
                                continue
                                
                            file_path = response_data["result"]["file_path"]
                            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

                            if media["type"] == "photo":
                                embed.set_image(url=download_url)
                                await channel.send(embed=embed)
                            elif media["type"] == "video":
                                video_filename = "telegram_video.mp4"
                                logger.info(f"Descargando video desde: {download_url}")
                                if download_video(download_url, video_filename):
                                    await channel.send(embed=embed)
                                    await channel.send(file=discord.File(video_filename))
                                    # Eliminar el archivo después de enviarlo
                                    if os.path.exists(video_filename):
                                        os.remove(video_filename)
                                else:
                                    # Si la descarga falla, enviar solo el texto
                                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error al procesar archivo multimedia: {str(e)}")
                    await channel.send(embed=embed)  # Enviar solo el embed si hay un error con el media
            else:
                # Si no hay media, solo enviar el texto
                await channel.send(embed=embed)
                
            await asyncio.sleep(1)  # Añadir pequeña pausa entre mensajes

    except Exception as e:
        logger.error(f"Error en check_telegram: {str(e)}")
        await asyncio.sleep(5)  # Esperar antes de reintentar

# Evento de inicio del bot de Discord
@bot.event
async def on_ready():
    logger.info(f"Bot de Discord conectado como {bot.user.name}")
    check_telegram.start()

# Manejador para comandos de prueba
@bot.command(name="test")
async def test_command(ctx):
    await ctx.send("Bot funcionando correctamente!")

# Ejecutar el bot de Discord
if __name__ == "__main__":
    logger.info("Iniciando bot...")
    bot.run(DISCORD_BOT_TOKEN)
