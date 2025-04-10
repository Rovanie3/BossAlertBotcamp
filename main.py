import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import json
import os
import logging
from dotenv import load_dotenv

# Primeiro configuramos o logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

# Agora carregamos as variáveis de ambiente
load_dotenv('token.env')  # Especificando o nome do arquivo .env

# Configurações do Bot com verificações
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logger.error("Token do Discord não encontrado! Verifique seu arquivo token.env")
    exit(1)

CHANNEL_ID = os.getenv('CHANNEL_ID')
if not CHANNEL_ID:
    logger.error("CHANNEL_ID não encontrado! Verifique seu arquivo token.env")
    exit(1)

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    logger.error(f"CHANNEL_ID inválido: {CHANNEL_ID} - deve ser um número")
    exit(1)

# Tempos de respawn dos bosses em horas
BOSS_RESPAWNS = {
    "Rotura": 12.5,    # 12 horas e 30 minutos
    "Stormid": 18,
    "Tigdal": 12.5,
    "Hakir": 13,
    "Daminos": 19 + 20/60  # 19 horas e 20 minutos
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
        
        self.boss_timers = {}  # Armazenará {'boss': minutos_restantes}
        self.last_spawn_time = {}  # Armazenará {'boss': datetime_do_ultimo_spawn}
        self.last_alerts = {}  # Controla os alertas já enviados
        self.load_data()

    def load_data(self):
        """Carrega dados salvos"""
        try:
            if os.path.exists('boss_data.json'):
                with open('boss_data.json', 'r') as f:
                    data = json.load(f)
                    self.boss_timers = data.get('timers', {})
                    self.last_spawn_time = {k: datetime.fromisoformat(v) if v else None 
                                          for k, v in data.get('spawn_times', {}).items()}
                    self.last_alerts = data.get('alerts', {})
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")
            self.reset_data()

    def save_data(self):
        """Salva os dados"""
        try:
            with open('boss_data.json', 'w') as f:
                json.dump({
                    'timers': self.boss_timers,
                    'spawn_times': {k: v.isoformat() if v else None 
                                   for k, v in self.last_spawn_time.items()},
                    'alerts': self.last_alerts
                }, f)
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")

    def reset_data(self):
        """Reseta todos os dados"""
        self.boss_timers = {boss: None for boss in BOSS_RESPAWNS}
        self.last_spawn_time = {boss: None for boss in BOSS_RESPAWNS}
        self.last_alerts = {boss: {} for boss in BOSS_RESPAWNS}

    async def setup_hook(self):
        """Configuração inicial do bot"""
        # Inicializa dados para todos os bosses
        for boss in BOSS_RESPAWNS:
            if boss not in self.boss_timers:
                self.boss_timers[boss] = None
            if boss not in self.last_spawn_time:
                self.last_spawn_time[boss] = None
            if boss not in self.last_alerts:
                self.last_alerts[boss] = {}
        
        self.alert_loop.start()

    async def on_ready(self):
        logger.info(f'Bot conectado como {self.user} (ID: {self.user.id})')
        logger.info(f'Conectado em {len(self.guilds)} servidor(es)')
        
        # Verifica se o canal existe
        channel = self.get_channel(CHANNEL_ID)
        if channel is None:
            logger.error(f"Canal com ID {CHANNEL_ID} não encontrado!")
        else:
            logger.info(f"Canal encontrado: {channel.name}")

        await self.tree.sync()

    async def close(self):
        self.save_data()
        await super().close()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
        """Verifica e envia alertas"""
        try:
            channel = self.get_channel(CHANNEL_ID)
            if channel is None:
                logger.warning("Canal não encontrado!")
                return

            now = datetime.now()
            
            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)
                
                if time_left is None or time_left <= 0:
                    continue
                
                # Verificar se precisa enviar alerta
                if time_left <= 60 and time_left % 10 == 0:
                    last_alert = self.last_alerts.get(boss, {}).get(time_left)
                    
                    if last_alert is None or (now - datetime.fromisoformat(last_alert)).total_seconds() > 300:
                        self.last_alerts.setdefault(boss, {})[time_left] = now.isoformat()
                        
                        if time_left == 0:
                            msg = f"🚨 **{boss} SPAWNOU!** @everyone"
                            tts_msg = f"O {boss} acabou de nascer, seus condenados! Corram antes que seja tarde!"
                            self.last_spawn_time[boss] = now
                            self.boss_timers[boss] = None
                        else:
                            msg = f"🔔 **{boss} vai nascer em {time_left} minutos!** @everyone"
                            tts_msg = f"O {boss} vai nascer em {time_left} minutos, seus condenados! Preparem-se!"
                        
                        await channel.send(msg)
                        await channel.send(tts_msg, tts=True)
                        
                        if time_left <= 30:
                            await self.send_status()
                
                # Atualiza o contador
                if time_left > 0:
                    self.boss_timers[boss] = max(0, time_left - 0.5)  # Diminui 0.5 minuto (30 segundos)
        except Exception as e:
            logger.error(f"Erro no alert_loop: {e}")

    async def send_status(self):
        """Envia status dos bosses"""
        try:
            channel = self.get_channel(CHANNEL_ID)
            if channel is None:
                return

            status_msg = "⏳ **Status dos Bosses:**\n"
            
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
            
            await channel.send(status_msg)
        except Exception as e:
            logger.error(f"Erro ao enviar status: {e}")

bot = BossBot()

@bot.hybrid_command(name="agora", description="Mostra o status atual dos bosses")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def agora(ctx):
    """Mostra o status atual dos bosses"""
    await bot.send_status()

@bot.hybrid_command(name="morreu", description="Registra a morte de um boss")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def morreu(ctx, boss_name: str):
    """Registra a morte de um boss"""
    if boss_name not in BOSS_RESPAWNS:
        valid_bosses = ", ".join(BOSS_RESPAWNS.keys())
        await ctx.send(f"❌ Boss inválido. Nomes válidos: {valid_bosses}")
        return
    
    respawn_hours = BOSS_RESPAWNS[boss_name]
    respawn_minutes = int(respawn_hours * 60)
    bot.boss_timers[boss_name] = respawn_minutes
    bot.last_spawn_time[boss_name] = None
    bot.last_alerts[boss_name] = {}
    bot.save_data()
    
    hours = int(respawn_hours)
    minutes = int((respawn_hours - hours) * 60)
    await ctx.send(
        f"✅ **{boss_name}** registrado como morto!\n"
        f"⏳ Nascerá em: {hours:02d}h{minutes:02d}m"
    )
    await bot.send_status()

@bot.hybrid_command(name="atualizar", description="Atualiza o tempo restante manualmente")
@commands.has_any_role("Admin", "Moderador", "Líder")
async def atualizar(ctx, boss_name: str, time_input: str):
    """Atualiza o tempo restante manualmente"""
    if boss_name not in BOSS_RESPAWNS:
        valid_bosses = ", ".join(BOSS_RESPAWNS.keys())
        await ctx.send(f"❌ Boss inválido. Nomes válidos: {valid_bosses}")
        return
    
    try:
        if ":" in time_input:
            hours, minutes = map(int, time_input.split(":"))
            time_left = hours * 60 + minutes
        else:
            time_left = int(time_input)
            
        bot.boss_timers[boss_name] = time_left
        bot.last_spawn_time[boss_name] = None
        bot.last_alerts[boss_name] = {}
        bot.save_data()
        
        hours = time_left // 60
        minutes = time_left % 60
        await ctx.send(
            f"✅ **{boss_name}** atualizado!\n"
            f"⏳ Tempo restante: {hours:02d}h{minutes:02d}m"
        )
        
        if time_left <= 60:
            await bot.alert_loop()
        
        await bot.send_status()
    except ValueError:
        await ctx.send("❌ Formato inválido. Use HH:MM ou apenas minutos")

@atualizar.error
@morreu.error
async def command_error(ctx, error):
    """Trata erros nos comandos"""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argumento faltando. Use: `!{ctx.command.name} <boss> <tempo>`")
    elif isinstance(error, commands.MissingRole):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
    else:
        await ctx.send(f"❌ Ocorreu um erro: {str(error)}")
        logger.error(f"Erro no comando {ctx.command.name}: {error}")

async def main():
    async with bot:
        try:
            logger.info("Iniciando bot...")
            await bot.start(TOKEN)
        except discord.LoginFailure:
            logger.error("Token inválido. Verifique seu token e tente novamente.")
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
        finally:
            if not bot.is_closed():
                await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")