# Bot de Discord para notificações de bosses, com modificação para aguardar 10 minutos após o spawn antes de resetar o timer.

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
    logger.error('Token não encontrado! Verifique token.env')
    exit(1)

# Lista de canais dos servidores
CHANNEL_IDS = [
    1359985623007629685,  # Servidor 1
    1352326383623340042,  # Servidor 2
    1359946007479324977   # Servidor 3
]

# Tempos de respawn dos bosses
BOSS_RESPAWNS = {
    'Rotura': 12.35,    # 12 horas e 25 minutos
    'Stomid': 18,
    'Tigdal': 12.25,
    'Hakir': 18.35,
    'Damiros': 19 + 20/60  # 19 horas e 20 minutos
}

class BossBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            activity=discord.Game(name='Monitorando Bosses')
        )
        
        self.boss_timers = {}  # Armazenará {'boss': minutos_restantes}
        self.last_spawn_time = {}  # Armazenará {'boss': datetime_do_ultimo_spawn}
        self.last_alerts = {}  # Controla os alertas já enviados
        self.load_data()  # Carrega os dados salvos

    def load_data(self):
        '''Carrega dados salvos do arquivo JSON'''
        try:
            if os.path.exists('boss_data.json'):
                with open('boss_data.json', 'r') as f:
                    data = json.load(f)
                    self.boss_timers = data.get('timers', {})
                    self.last_spawn_time = {k: datetime.fromisoformat(v) if v else None 
                                          for k, v in data.get('spawn_times', {}).items()}
                    self.last_alerts = data.get('alerts', {})
        except Exception as e:
            logger.error(f'Erro ao carregar dados: {e}')
            self.reset_data()

    def save_data(self):
        '''Salva os dados no arquivo JSON'''
        try:
            with open('boss_data.json', 'w') as f:
                json.dump({
                    'timers': self.boss_timers,
                    'spawn_times': {k: v.isoformat() if v else None 
                                   for k, v in self.last_spawn_time.items()},
                    'alerts': self.last_alerts
                }, f)
        except Exception as e:
            logger.error(f'Erro ao salvar dados: {e}')

    def reset_data(self):
        '''Reseta todos os dados para valores padrão'''
        self.boss_timers = {boss: None for boss in BOSS_RESPAWNS}
        self.last_spawn_time = {boss: None for boss in BOSS_RESPAWNS}
        self.last_alerts = {boss: {} for boss in BOSS_RESPAWNS}

    async def setup_hook(self):
        '''Configuração inicial do bot'''
        # Inicializa dados para todos os bosses
        for boss in BOSS_RESPAWNS:
            if boss not in self.boss_timers:
                self.boss_timers[boss] = None
            if boss not in self.last_spawn_time:
                self.last_spawn_time[boss] = None
            if boss not in self.last_alerts:
                self.last_alerts[boss] = {}
        
        self.alert_loop.start()
        self.hourly_update.start()  # Nova tarefa periódica

    async def on_ready(self):
        logger.info(f'Bot conectado como {self.user} (ID: {self.user.id})')
        logger.info(f'Conectado em {len(self.guilds)} servidor(es)')
        
        # Verifica todos os canais configurados
        for channel_id in CHANNEL_IDS:
            channel = self.get_channel(channel_id)
            if channel is None:
                logger.error(f'Canal com ID {channel_id} não encontrado!')
            else:
                logger.info(f'Canal encontrado: {channel.name} (ID: {channel.id})')

        await self.tree.sync()

    async def close(self):
        self.save_data()
        await super().close()

    @tasks.loop(seconds=30)
    async def alert_loop(self):
        '''Envia alertas para TODOS os servidores configurados'''
        try:
            now = datetime.now()

            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)

                if time_left is None or time_left < 0:
                    continue

                # Verificar se precisa enviar alerta
                if time_left <= 30 and time_left % 10 == 0:
                    last_alert = self.last_alerts.get(boss, {}).get(time_left)

                    if last_alert is None or (now - datetime.fromisoformat(last_alert)).total_seconds() > 300:
                        self.last_alerts.setdefault(boss, {})[time_left] = now.isoformat()
                        logger.info(f'Alerta disparado: {boss} em {time_left} minutos')

                        for channel_id in CHANNEL_IDS:
                            channel = self.get_channel(channel_id)
                            if channel:
                                if time_left == 0:
                                    msg = f'🚨 **{boss} SPAWNOU!** @everyone'
                                    tts_msg = f'O {boss} acabou de nascer, seus condenados! Corram antes que seja tarde!'
                                    self.last_spawn_time[boss] = now

                                    # Aguarda 10 minutos antes de reiniciar o timer
                                    async def reset_boss_timer(boss_name):
                                        logger.info(f'Aguardando 10 minutos antes de reiniciar o timer de {boss_name}...')
                                        await asyncio.sleep(600)  # 10 minutos
                                        self.boss_timers[boss_name] = int(BOSS_RESPAWNS[boss_name] * 60)
                                        self.last_alerts[boss_name] = {}
                                        self.save_data()
                                        logger.info(f'Timer do boss {boss_name} reiniciado automaticamente.')

                                    asyncio.create_task(reset_boss_timer(boss))

                                else:
                                    msg = f'🔔 **{boss} vai nascer em {time_left} minutos!** @everyone'
                                    tts_msg = f'O {boss} vai nascer em {time_left} minutos, seus condenados! Preparem-se!'

                                await channel.send(msg)
                                await channel.send(tts_msg, tts=True)

                # Atualiza o contador
                if time_left > 0:
                    self.boss_timers[boss] = max(0, time_left - 0.5)  # Diminui 0.5 minuto (30 segundos)

        except Exception as e:
            logger.error(f'Erro no alert_loop: {e}')

    @tasks.loop(hours=1)
    async def hourly_update(self):
        '''Envia atualização geral de status a cada hora'''
        try:
            logger.info('Enviando atualização horária dos bosses')
            await self.send_status()
        except Exception as e:
            logger.error(f'Erro no hourly_update: {e}')

    async def send_status(self, ctx=None):
        '''Envia status para todos os servidores ou para um comando específico'''
        try:
            status_msg = '⏳ **Status Global dos Bosses:**\\n'

            for boss in BOSS_RESPAWNS:
                time_left = self.boss_timers.get(boss)

                if time_left is None:
                    status = '🔴 Sem dados'
                elif time_left <= 0:
                    status = '🟢 SPAWNOU!'
                else:
                    hours = int(time_left // 60)
                    minutes = int(time_left % 60)
                    status = f'{hours:02d}h{minutes:02d}m'

                status_msg += f'- **{boss}**: {status}\\n'

            if ctx:
                await ctx.send(status_msg)
            else:
                for channel_id in CHANNEL_IDS:
                    channel = self.get_channel(channel_id)
                    if channel:
                        await channel.send(status_msg)
        except Exception as e:
            logger.error(f'Erro ao enviar status: {e}')

bot = BossBot()

@bot.hybrid_command(name='agora', description='Mostra o status atual dos bosses em todos servidores')
@commands.has_any_role('Admin', 'Moderador', 'Líder', 'Lider')
async def agora(ctx):
    '''Mostra o status atual dos bosses'''
    await bot.send_status(ctx)

@bot.hybrid_command(name='morreu', description='Registra a morte de um boss em todos servidores')
@commands.has_any_role('Admin', 'Moderador', 'Líder', 'Lider')
async def morreu(ctx, boss_name: str):
    '''Registra a morte de um boss'''
    if boss_name not in BOSS_RESPAWNS:
        await ctx.send(f'Boss {boss_name} não encontrado.')
        return

    bot.boss_timers[boss_name] = int(BOSS_RESPAWNS[boss_name] * 60)
    bot.last_alerts[boss_name] = {}
    bot.save_data()
    await ctx.send(f'Boss {boss_name} morreu. Timer reiniciado.')

bot.run(TOKEN)
