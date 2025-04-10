import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import json
import os
import logging
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

# Carrega variáveis de ambiente
load_dotenv('token.env')

# Verificação do token
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logger.error("Token não encontrado! Verifique token.env")
    exit(1)

# Lista de canais dos servidores
CHANNEL_IDS = [
    1359985623007629685,  # Servidor 1
    1352326383623340042,  # Servidor 2
    1359946007479324977   # Servidor 3
]

# Tempos de respawn dos bosses
BOSS_RESPAWNS = {
    "Rotura": 12.5,
    "Stormid": 18,
    "Tigdal": 12.5,
    "Hakir": 13,
    "Daminos": 19 + 20/60
}

class BossBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Game(name="Monitorando Bosses")
        )
        
        self.boss_timers = {}
        self.last_spawn_time = {}
        self.last_alerts = {}
        self.load_data()

    # ... (Mantenha os métodos load_data, save_data, reset_data IGUAIS ao seu original)

    async def setup_hook(self):
        """Configuração inicial"""
        for boss in BOSS_RESPAWNS:
            if boss not in self.boss_timers:
                self.boss_timers[boss] = None
            if boss not in self.last_spawn_time:
                self.last_spawn_time[boss] = None
            if boss not in self.last_alerts:
                self.last_alerts[boss] = {}
        
        self.alert_loop.start()

    async def on_ready(self):
        logger.info(f'Bot conectado como {self.user}')
        logger.info(f'Conectado em {len(self.guilds)} servidores')
        
        # Verifica todos os canais
        for channel_id in CHANNEL_IDS:
            channel = self.get_channel(channel_id)
            if channel:
                logger.info(f'Canal {channel.name} ({channel.id}) pronto!')
            else:
                logger.warning(f'Canal {channel_id} não encontrado!')
        
        await self.tree.sync()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
        """Envia alertas para TODOS os servidores"""
        try:
            now = datetime.now()
            
            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)
                
                if time_left is None or time_left <= 0:
                    continue
                
                if time_left <= 60 and time_left % 10 == 0:
                    last_alert = self.last_alerts.get(boss, {}).get(time_left)
                    
                    if last_alert is None or (now - datetime.fromisoformat(last_alert)).total_seconds() > 300:
                        self.last_alerts.setdefault(boss, {})[time_left] = now.isoformat()
                        
                        for channel_id in CHANNEL_IDS:
                            channel = self.get_channel(channel_id)
                            if channel:
                                if time_left == 0:
                                    msg = f"🚨 **{boss} SPAWNOU!** @everyone"
                                    tts_msg = f"{boss} nasceu! Corram!"
                                    self.last_spawn_time[boss] = now
                                    self.boss_timers[boss] = None
                                else:
                                    msg = f"🔔 **{boss} em {int(time_left)} minutos!** @everyone"
                                    tts_msg = f"{boss} em {int(time_left)} minutos!"
                                
                                await channel.send(msg)
                                await channel.send(tts_msg, tts=True)
                
                if time_left > 0:
                    self.boss_timers[boss] = max(0, time_left - 0.5)
                    
        except Exception as e:
            logger.error(f"Erro no alert_loop: {e}")

    async def send_status(self, ctx=None):
        """Envia status para todos os canais ou para um comando específico"""
        try:
            status_msg = "⏳ **Status Global dos Bosses:**\n"
            
            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)
                
                if time_left is None:
                    status = "🔴 Sem dados"
                elif time_left <= 0:
                    status = "🟢 SPAWNOU!"
                else:
                    hours = int(time_left // 60)
                    minutes = int(time_left % 60)
                    status = f"{hours:02d}h{minutes:02d}m"
                
                status_msg += f"- **{boss}**: {status}\n"
            
            if ctx:
                await ctx.send(status_msg)
            else:
                for channel_id in CHANNEL_IDS:
                    channel = self.get_channel(channel_id)
                    if channel:
                        await channel.send(status_msg)
                        
        except Exception as e:
            logger.error(f"Erro ao enviar status: {e}")

bot = BossBot()

# Comandos (mantidos como no original, mas agora afetam todos servidores)
@bot.hybrid_command(name="agora", description="Mostra status em todos servidores")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def agora(ctx):
    await bot.send_status(ctx)

@bot.hybrid_command(name="morreu", description="Registra morte GLOBAL de um boss")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def morreu(ctx, boss_name: str):
    if boss_name not in BOSS_RESPAWNS:
        await ctx.send(f"❌ Boss inválido. Use: {', '.join(BOSS_RESPAWNS.keys())}")
        return
    
    respawn_minutes = int(BOSS_RESPAWNS[boss_name] * 60)
    bot.boss_timers[boss_name] = respawn_minutes
    bot.save_data()
    
    await ctx.send(f"✅ **{boss_name}** registrado GLOBALMENTE!")
    await bot.send_status()

@bot.hybrid_command(name="atualizar", description="Atualiza tempo manualmente")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def atualizar(ctx, boss_name: str, time_input: str):
    if boss_name not in BOSS_RESPAWNS:
        await ctx.send(f"❌ Boss inválido. Use: {', '.join(BOSS_RESPAWNS.keys())}")
        return
    
    try:
        if ":" in time_input:
            hours, minutes = map(int, time_input.split(":"))
            time_left = hours * 60 + minutes
        else:
            time_left = int(time_input)
            
        bot.boss_timers[boss_name] = time_left
        bot.save_data()
        
        await ctx.send(f"✅ **{boss_name}** atualizado GLOBALMENTE!")
        await bot.send_status()
    except ValueError:
        await ctx.send("❌ Formato inválido. Use HH:MM ou minutos")

# (Mantenha os tratamentos de erro como no seu original)

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
