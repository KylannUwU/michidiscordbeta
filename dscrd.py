import discord
from discord.ext import commands, tasks
import aiohttp
from openai import OpenAI
from bs4 import BeautifulSoup
import re
import traceback
from dotenv import load_dotenv
import os
import json
import datetime

# Cargar variables de entorno
load_dotenv()

TOKEN = os.getenv("TOKEN")
CANAL_AVISOS = int(os.getenv("CANAL_AVISOS"))
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_OAUTH_TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRACKER_API_KEY = os.getenv("TRACKER_API_KEY")

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

config = load_config()

CLIP_CATEGORY_NAME = "CLIPS EDIT"

# Inicializar el bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Inicializar OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

rank_translation = {
    "Iron 1": ("Hierro 1", "🛠️"), "Iron 2": ("Hierro 2", "🛠️"), "Iron 3": ("Hierro 3", "🛠️"),
    "Bronze 1": ("Bronce 1", "🥉"), "Bronze 2": ("Bronce 2", "🥉"), "Bronze 3": ("Bronce 3", "🥉"),
    "Silver 1": ("Plata 1", "🥈"), "Silver 2": ("Plata 2", "🥈"), "Silver 3": ("Plata 3", "🥈"),
    "Gold 1": ("Oro 1", "🥇"), "Gold 2": ("Oro 2", "🥇"), "Gold 3": ("Oro 3", "🥇"),
    "Platinum 1": ("Platino 1", "💎"), "Platinum 2": ("Platino 2", "💎"), "Platinum 3": ("Platino 3", "💎"),
    "Diamond 1": ("Diamante 1", "💎"), "Diamond 2": ("Diamante 2", "💎"), "Diamond 3": ("Diamante 3", "💎"),
    "Immortal 1": ("Inmortal 1", "⚡"), "Immortal 2": ("Inmortal 2", "⚡"), "Immortal 3": ("Inmortal 3", "⚡"),
    "Radiant": ("Radiante", "🌟"),
}

class ClipButtons(discord.ui.View):
    def __init__(self, clip_url):
        super().__init__(timeout=None)
        self.clip_url = clip_url

    @discord.ui.button(label="Mover a edit", style=discord.ButtonStyle.success)
    async def move_to_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        channel_name = f"clips-edit-{today}"

        category = discord.utils.get(guild.categories, name=CLIP_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(CLIP_CATEGORY_NAME)

        target_channel = discord.utils.get(category.text_channels, name=channel_name)
        if not target_channel:
            target_channel = await guild.create_text_channel(channel_name, category=category)

        await target_channel.send(f"🎬 {self.clip_url}")
        await interaction.message.delete()
        await interaction.response.send_message(f"✅ Clip movido a #{channel_name}", ephemeral=True)

    @discord.ui.button(label="Eliminar", style=discord.ButtonStyle.danger)
    async def delete_clip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("❌ Clip eliminado", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Se han registrado {len(synced)} comandos de aplicación.")
    except Exception as e:
        print(f"⚠️ Error al sincronizar comandos: {e}")
    clean_empty_edit_channels.start()

@bot.tree.command(name="set", description="Configura este canal como canal principal de clips")
@discord.app_commands.describe(tipo="Selecciona qué quieres configurar (solo acepta 'main')")
async def set_channel(interaction: discord.Interaction, tipo: str):
    if tipo.lower() != "main":
        await interaction.response.send_message("❌ Tipo no reconocido. Usa `/set main`", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    config[guild_id] = {
        "suggestion_channel_id": interaction.channel.id
    }
    save_config(config)
    await interaction.response.send_message(f"✅ Este canal ha sido configurado como canal principal de clips.", ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)
    if guild_id not in config:
        return

    suggestion_channel_id = config[guild_id].get("suggestion_channel_id")
    if message.channel.id != suggestion_channel_id:
        return

    if "clips.twitch.tv" in message.content:
        view = ClipButtons(message.content.strip())
        await message.channel.send(f"📎 Clip detectado:\n{message.content.strip()}", view=view)

    await bot.process_commands(message)

@tasks.loop(minutes=5)
async def clean_empty_edit_channels():
    for guild in bot.guilds:
        category = discord.utils.get(guild.categories, name=CLIP_CATEGORY_NAME)
        if category:
            for channel in category.text_channels:
                try:
                    async for _ in channel.history(limit=1):
                        break
                    else:
                        await channel.delete()
                        print(f"🧹 Canal vacío eliminado: {channel.name}")
                except Exception as e:
                    print(f"⚠️ Error al revisar canal {channel.name}: {e}")

# Verificar si un canal de Twitch está en vivo (ASYNC)
async def is_twitch_live(channel_name):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_OAUTH_TOKEN}'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'https://api.twitch.tv/helix/streams?user_login={channel_name}',
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return len(data.get('data', [])) > 0
                return False
    except Exception as e:
        print(f"⚠️ Error al verificar Twitch: {e}")
        return False

# Comando /islive
@bot.tree.command(name="islive", description="Verifica si un canal de Twitch está en vivo.")
async def islive(interaction: discord.Interaction, canal: str):
    await interaction.response.defer()
    try:
        if await is_twitch_live(canal):
            await interaction.followup.send(f'🎥 El canal **{canal}** está en vivo en Twitch: https://www.twitch.tv/{canal}')
        else:
            await interaction.followup.send(f'❌ El canal **{canal}** no está en vivo en este momento.')
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error al verificar el estado del canal: {e}")
        traceback.print_exc()

# Comando /answer - IA de OpenAI
@bot.tree.command(name="answer", description="Pregunta algo a la IA y recibe una respuesta.")
async def answer(interaction: discord.Interaction, pregunta: str):
    await interaction.response.defer()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": pregunta}]
        )
        contenido = response.choices[0].message.content
    except Exception as e:
        traceback.print_exc()
        contenido = "⚠️ Ocurrió un error al procesar la respuesta."
    await interaction.followup.send(contenido)

# Comando /valrank (ASYNC con aiohttp)
@bot.tree.command(name="valrank", description="Obtén el rango de un jugador de Valorant.")
async def valrank(interaction: discord.Interaction, region: str, name: str, tag: str):
    await interaction.response.defer()
    url = f"https://splendid-groovy-feverfew.glitch.me/valorant/{region}/{name}/{tag}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    data = await response.text()
                    data = data.strip()
                    print("Respuesta del servidor:", data)
                    match = re.search(r"([a-zA-Z0-9#]+) \[(.*?)\] : (\d+) RR", data)
                    
                    if match:
                        player_name = match.group(1).split('#')[0]
                        rank = match.group(2)
                        rating = match.group(3)
                        
                        if rank in rank_translation:
                            translated_rank, emoji = rank_translation[rank]
                            await interaction.followup.send(
                                f"Rango de {player_name}: {emoji} {translated_rank}\n📊 Rating: {rating} RR"
                            )
                        else:
                            await interaction.followup.send(
                                f"Rango de {player_name}: {rank} (No traducido)\n📊 Rating: {rating} RR"
                            )
                    else:
                        await interaction.followup.send(
                            "❌ No se pudo extraer la información del jugador. Formato inesperado."
                        )
                else:
                    await interaction.followup.send(f"❌ Error al consultar: código {response.status}")
                    
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⏱️ La solicitud tardó demasiado tiempo. El servidor puede estar lento. Intenta de nuevo."
        )
    except aiohttp.ClientError as e:
        await interaction.followup.send(
            "❌ No se pudo conectar al servidor. Puede estar caído o no disponible."
        )
        print(f"Error de conexión: {e}")
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error inesperado: {e}")
        traceback.print_exc()

# Tarea en segundo plano (comentada por ahora)
# @tasks.loop(minutes=5)
# async def check_tiktok_live():
#     canal = bot.get_channel(CANAL_AVISOS)
#     if canal and is_tiktok_live(TIKTOK_USERNAME):
#         mensaje = f"🚨 {TIKTOK_USERNAME} está en **vivo** en TikTok!\n🔴 https://www.tiktok.com/@{TIKTOK_USERNAME}/live"
#         await canal.send(mensaje)

# Iniciar el bot
bot.run(TOKEN)
