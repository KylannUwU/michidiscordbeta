import discord
from discord.ext import commands, tasks
import requests
import openai  # Asegúrate de instalarlo con pip install openai
from bs4 import BeautifulSoup
import re  # Asegúrate de importar 're' para las expresiones regulares
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
CANAL_AVISOS = int(os.getenv("CANAL_AVISOS"))
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME")

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_OAUTH_TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRACKER_API_KEY = os.getenv("TRACKER_API_KEY")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


openai.api_key = OPENAI_API_KEY  # Configuración de OpenAI




rank_translation = {
    "Iron 1": ("Hierro 1", "🛠️"),
    "Iron 2": ("Hierro 2", "🛠️"),
    "Iron 3": ("Hierro 3", "🛠️"),
    "Bronze 1": ("Bronce 1", "🥉"),
    "Bronze 2": ("Bronce 2", "🥉"),
    "Bronze 3": ("Bronce 3", "🥉"),
    "Silver 1": ("Plata 1", "🥈"),
    "Silver 2": ("Plata 2", "🥈"),
    "Silver 3": ("Plata 3", "🥈"),
    "Gold 1": ("Oro 1", "🥇"),
    "Gold 2": ("Oro 2", "🥇"),
    "Gold 3": ("Oro 3", "🥇"),
    "Platinum 1": ("Platino 1", "💎"),
    "Platinum 2": ("Platino 2", "💎"),
    "Platinum 3": ("Platino 3", "💎"),
    "Diamond 1": ("Diamante 1", "💎"),
    "Diamond 2": ("Diamante 2", "💎"),
    "Diamond 3": ("Diamante 3", "💎"),
    "Immortal 1": ("Inmortal 1", "⚡"),
    "Immortal 2": ("Inmortal 2", "⚡"),
    "Immortal 3": ("Inmortal 3", "⚡"),
    "Radiant": ("Radiante", "🌟"),
}





@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Se han registrado {len(synced)} comandos de aplicación.")
    except Exception as e:
        print(f"⚠️ Error al sincronizar comandos: {e}")

    # check_tiktok_live.start()

# Función para verificar si un canal de Twitch está en vivo
def is_twitch_live(channel_name):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_OAUTH_TOKEN}'
    }
    response = requests.get(f'https://api.twitch.tv/helix/streams?user_login={channel_name}', headers=headers)
    data = response.json()
    return len(data['data']) > 0  

# Comando /status para verificar el estado de un canal de Twitch
@bot.tree.command(name="islive", description="Verifica si un canal de Twitch está en vivo.")
async def islive(interaction: discord.Interaction, canal: str):
    if is_twitch_live(canal):
        await interaction.response.send_message(f'🎥 El canal **{canal}** está en vivo en Twitch: https://www.twitch.tv/{canal}')
    else:
        await interaction.response.send_message(f'❌ El canal **{canal}** no está en vivo en este momento.')

#Comando /answer para responder con IA
@bot.tree.command(name="answer", description="Pregunta algo a la IA y recibe una respuesta.")
async def answer(interaction: discord.Interaction, pregunta: str):
    await interaction.response.defer()  # Indica que la respuesta está en proceso
    
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": pregunta}]
        )
        mensaje_respuesta = respuesta['choices'][0]['message']['content']
    except Exception as e:
        mensaje_respuesta = f"⚠️ Ocurrió un error al procesar la respuesta"

    await interaction.followup.send(mensaje_respuesta)

# Comando /valrank para obtener el rango actual de un jugador de Valorant
@bot.tree.command(name="valrank", description="Obtén el rango de un jugador de Valorant.")
async def valrank(interaction: discord.Interaction, region: str, name: str, tag: str):
    url = f"https://splendid-groovy-feverfew.glitch.me/valorant/{region}/{name}/{tag}"

    try:
        # Realiza la solicitud HTTP
        response = requests.get(url)

        # Verifica que la respuesta sea exitosa (código de estado 200)
        if response.status_code == 200:
            # La respuesta es una cadena de texto, no un JSON
            data = response.text.strip()  # Removemos cualquier espacio o salto de línea extra

            # Imprime la respuesta para verificar el formato
            print("Respuesta del servidor:", data)

            # Usamos una expresión regular para extraer el rango y rating
            match = re.search(r"([a-zA-Z0-9#]+) \[(.*?)\] : (\d+) RR", data)

            if match:
                player_name = match.group(1).split('#')[0]  # Elimina el tag y mantiene solo el nombre
                rank = match.group(2)
                rating = match.group(3)

                # Traducimos el rango y agregamos el emoji correspondiente
                if rank in rank_translation:
                    translated_rank, emoji = rank_translation[rank]
                    await interaction.response.send_message(f"Rango de {player_name}: {emoji} {translated_rank}\n📊 Rating: {rating} RR")
                else:
                    await interaction.response.send_message(f"Rango de {player_name}: {rank} (No traducido)\n📊 Rating: {rating} RR")
            else:
                await interaction.response.send_message("❌ No se pudo extraer la información del jugador. Formato inesperado.")

        else:
            await interaction.response.send_message(f"❌ No se pudo obtener la información del jugador. Código de estado: {response.status_code}")

    except requests.exceptions.RequestException as e:
        await interaction.response.send_message(f"⚠️ Error al realizar la solicitud: {e}")
# Tarea en segundo plano para monitorear TikTok cada 5 minutos
# @tasks.loop(minutes=5)
# async def check_tiktok_live():
#     canal = bot.get_channel(CANAL_AVISOS)
#     if canal and is_tiktok_live(TIKTOK_USERNAME):
#         mensaje = f"🚨 {TIKTOK_USERNAME} está en **vivo** en TikTok!\n🔴 Mira el stream aquí: https://www.tiktok.com/@{TIKTOK_USERNAME}/live"
#         await canal.send(mensaje)

bot.run(TOKEN)