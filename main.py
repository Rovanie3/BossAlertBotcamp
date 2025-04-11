import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import os
import logging
from dotenv import load_dotenv

# Configuração básica
load_dotenv('token.env')
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError("Token não encontrado!")

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
        """Carrega dados do arquivo JSON"""
        try:
            if os.path.exists('boss_data.json'):
                with open('boss_data.json', 'r') as f:
                    self.boss_data = json.load(f)
                    logger.info("Dados carregados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")
            self.reset_data()

    def save_data(self):
        """Salva dados no arquivo JSON"""
        try:
            with open('boss_data.json', 'w') as f:
                json.dump(self.boss_data, f)
            logger.info("Dados salvos com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")

    def reset_data(self):
        """Reseta todos os dados"""
        self.boss_data = {
            "timers": {boss: None for boss in BOSS_RESPAWNS},
            "spawn_times": {boss: None for boss in BOSS_RESPAWNS},
            "alerts": {boss: {} for boss in BOSS_RESPAWNS}
        }
        logger.info("Dados resetados")

    async def setup_hook(self):
        """Configuração inicial"""
        self.alert_loop.start()
        self.hourly_update.start()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
        """Loop principal de alertas"""
        try:
            now = datetime.now()
            for boss in BOSS_RESPAWNS:
                # ... (implementação do loop de alertas)
                pass
        except Exception as e:
            logger.error(f"Erro no alert_loop: {e}")

    # ... (restante dos métodos)

bot = BossBot()

@bot.event
async def on_ready():
    logger.info(f'Bot conectado como {bot.user}')

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
