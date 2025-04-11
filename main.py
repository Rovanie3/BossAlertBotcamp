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
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logger.error("Token não encontrado! Verifique token.env")
    exit(1)

# Configurações globais
CHANNEL_IDS = [1359985623007629685, 1352326383623340042, 1359946007479324977]
BOSS_RESPAWNS = {
    "Rotura": 12.5,    # 12h30m
    "Stormid": 18,
    "Tigdal": 12.5,
    "Hakir": 13,
    "Daminos": 19 + 20/60  # 19h20m
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

    # ... (métodos load_data, save_data, reset_data permanecem iguais)

    async def setup_hook(self):
        for boss in BOSS_RESPAWNS:
            self.boss_timers.setdefault(boss, None)
            self.last_spawn_time.setdefault(boss, None)
            self.last_alerts.setdefault(boss, {})
        
        self.alert_loop.start()
        self.hourly_update.start()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
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
                        logger.info(f"Alerta disparado: {boss} em {time_left} minutos")
                        
                        for channel_id in CHANNEL_IDS:
                            channel = self.get_channel(channel_id)
                            if channel:
                                if time_left == 0:
                                    msg = f"🚨 **{boss} SPAWNOU!** @everyone"
                                    self.last_spawn_time[boss] = now
                                    self.boss_timers[boss] = BOSS_RESPAWNS[boss] * 60
                                else:
                                    msg = f"🔔 **{boss} em {time_left} minutos!** @everyone"
                                await channel.send(msg)

                if time_left > 0:
                    self.boss_timers[boss] = max(0, time_left - 0.5)
        except Exception as e:
            logger.error(f"Erro no alert_loop: {e}")

    @tasks.loop(hours=1)
    async def hourly_update(self):
        try:
            logger.info("Enviando atualização horária")
            await self.send_status()
        except Exception as e:
            logger.error(f"Erro no hourly_update: {e}")

    async def send_status(self, ctx=None):
        try:
            embed = discord.Embed(title="⏳ Status dos Bosses", color=0x00FF00)
            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)
                status = "🟢 SPAWNOU!" if time_left == 0 else \
                         f"🟠 {int(time_left//60)}h{int(time_left%60):02d}m" if time_left else "🔴 Sem dados"
                embed.add_field(name=boss, value=status, inline=True)
            
            target = ctx or self.get_channel(CHANNEL_IDS[0])
            await target.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao enviar status: {e}")

bot = BossBot()

@bot.hybrid_command(name="agora", description="Mostra status dos bosses")
async def agora(ctx):
    """Versão pública do comando"""
    try:
        await bot.send_status(ctx)
    except Exception as e:
        await ctx.send("🔧 Erro ao buscar status. Tente novamente!", ephemeral=True)
        logger.error(f"Erro em !agora: {e}")

@bot.hybrid_command(name="admin_agora", description="[ADMIN] Status detalhado")
@commands.has_any_role("Admin", "Moderador", "Líder", "Lider", "Mod", "Administrador")
async def admin_agora(ctx):
    """Versão com permissões especiais"""
    try:
        await bot.send_status(ctx)
        logger.info(f"Comando admin_agora usado por {ctx.author}")
    except Exception as e:
        await ctx.send("❌ Erro interno. Verifique logs.", ephemeral=True)
        logger.error(f"Erro em admin_agora: {e}")

@admin_agora.error
async def admin_agora_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send(
            "⚠️ Você precisa ser:\n"
            "- Admin\n"
            "- Moderador\n"
            "- Líder\n\n"
            "Peça para atualizarem meus cargos permitidos!",
            ephemeral=True
        )
    else:
        await ctx.send("⚙️ Erro desconhecido. Contate um admin.", ephemeral=True)

# ... (comandos morreu, atualizar permanecem iguais)

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
