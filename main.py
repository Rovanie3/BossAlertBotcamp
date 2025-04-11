import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio  # Esta era a linha faltante!
import json
import os
import logging
from dotenv import load_dotenv

# Configuração básica
load_dotenv('token.env')
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError("Token não encontrado!")

# Configuração de bosses
BOSS_RESPAWNS = {
    "Rotura": 12.5,
    "Stormid": 18,
    "Tigdal": 12.5,
    "Hakir": 13,
    "Daminos": 19 + 20/60
}

CHANNEL_IDS = [1359985623007629685, 1352326383623340042, 1359946007479324977]

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

class BossBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Game(name="Monitorando Bosses")
        )
        self.boss_data = {
            "timers": {},
            "spawn_times": {},
            "alerts": {}
        }
        self.load_data()

    def load_data(self):
        try:
            if os.path.exists('boss_data.json'):
                with open('boss_data.json', 'r') as f:
                    self.boss_data = json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")
            self.reset_data()

    def save_data(self):
        try:
            with open('boss_data.json', 'w') as f:
                json.dump(self.boss_data, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")

    def reset_data(self):
        self.boss_data = {
            "timers": {boss: None for boss in BOSS_RESPAWNS},
            "spawn_times": {boss: None for boss in BOSS_RESPAWNS},
            "alerts": {boss: {} for boss in BOSS_RESPAWNS}
        }

    async def setup_hook(self):
        self.alert_loop.start()
        self.hourly_update.start()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
        try:
            now = datetime.now()
            for boss, timer in self.boss_data["timers"].items():
                if timer and timer > 0:
                    # Lógica de alertas aqui
                    pass
        except Exception as e:
            logger.error(f"Erro no alert_loop: {e}")

    @tasks.loop(hours=1)
    async def hourly_update(self):
        await self.send_status()

    async def send_status(self, ctx=None):
        embed = discord.Embed(title="Status dos Bosses", color=0x00ff00)
        for boss in BOSS_RESPAWNS:
            timer = self.boss_data["timers"].get(boss)
            status = "🟢 Pronto!" if timer == 0 else f"🟠 {timer}min" if timer else "🔴 Indisponível"
            embed.add_field(name=boss, value=status, inline=False)
        
        if ctx:
            await ctx.send(embed=embed)
        else:
            for channel_id in CHANNEL_IDS:
                channel = self.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

bot = BossBot()

@bot.event
async def on_ready():
    logger.info(f'Bot conectado como {bot.user}')

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
