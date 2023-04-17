import os
import dotenv
import re
import requests
import json
import hikari
from hikari import Color
import logging
import lavalink
import lightbulb
from lightbulb.ext import tasks
from googleapiclient.discovery import build

from ext_lib.utils import MusicCommandError, SongRequestsEnabledError
from ext_lib.MusicCommand import MusicCommand

from ext_lib.youtube_api_client import YouTubeSearchClient

dotenv.load_dotenv()

url_rx = re.compile(r'https?://(?:www\.)?.+')

youtube = YouTubeSearchClient()
   
music_plugin = lightbulb.Plugin("music_plugin", "🎧 Music commands")  
    
class EventHandler:
    """Events from the Lavalink server"""
    
    @lavalink.listener(lavalink.TrackStartEvent)
    async def track_start(self, event: lavalink.TrackStartEvent):

        player = music_plugin.bot.d.lavalink.player_manager.get(event.player.guild_id)
        
        # await music_plugin.bot.update_presence(
        #     activity = hikari.Activity(
        #     name = f"{player.current.author} - {player.current.title}",
        #     type = hikari.ActivityType.LISTENING
        # ))

        logging.info("Track started on guild: %s", event.player.guild_id)

    @lavalink.listener(lavalink.TrackEndEvent)
    async def track_end(self, event: lavalink.TrackEndEvent):

        player = music_plugin.bot.d.lavalink.player_manager.get(event.player.guild_id)

        # if not player.queue:
        #     await music_plugin.bot.update_presence(
        #         activity = hikari.Activity(
        #             name=f"/play",
        #             type=hikari.ActivityType.LISTENING
        #         ))

        logging.info("Track finished on guild: %s", event.player.guild_id)

    @lavalink.listener(lavalink.TrackExceptionEvent)
    async def track_exception(self, event: lavalink.TrackExceptionEvent):
        logging.warning("Track exception event happened on guild: %d", event.player.guild_id)

    @lavalink.listener(lavalink.QueueEndEvent)
    async def queue_finish(self, event: lavalink.QueueEndEvent):
        pass

async def sr_is_enabled(ctx: lightbulb.Context) -> bool:
    user_roles = ctx.member.role_ids
    if music_plugin.bot.d.sr and not (int(os.environ['ROLE_OWNER']) in user_roles or int(os.environ['ROLE_MOD']) in user_roles):
        raise SongRequestsEnabledError(':warning: Команда не может быть использована, пока играют треки сабов!')
    return True

sr_check = lightbulb.Check(p_callback=sr_is_enabled, s_callback=sr_is_enabled)

@tasks.task(s=.5, auto_start=True)
async def music_handler() -> None:
    if music_plugin.bot.d.lavalink:
        player = music_plugin.bot.d.lavalink.player_manager.get(music_plugin.bot.default_enabled_guilds[0])
        if music_plugin.bot.d.sr:
            if not player or not player.is_playing:
                response = requests.get('http://localhost/api/sr/get-queue')
                if response.status_code == 200:
                    data = response.json()
                    if len(data) > 0:
                        await music_plugin.bot.d.music._play(music_plugin.bot.default_enabled_guilds[0], 392227020202835970, data[0]['url'])
                        requests.post('http://localhost/api/sr/set-played', {'id' : data[0]['id']})
        if player:
            closed_connections = set()
            for ws_client in music_plugin.bot.d.music_subscribe_pool:
                try:
                    await ws_client.send(json.dumps({
                        'title' : player.current.title,
                        'artists' : player.current.author,
                        'duration' : int(player.current.duration / 1000),
                        'progress' : int(player.position / 1000),
                        'cover_path' : f'https://i.ytimg.com/vi/{player.current.identifier}/hqdefault.jpg',
                        'uri' : player.current.uri,
                        'requester' : player.current.extra['requester']
                    } if player.is_playing else {}))
                except:
                    closed_connections.add(ws_client)
            for conn in closed_connections:
                music_plugin.bot.d.music_subscribe_pool.remove(conn)


# on ready, connect to lavalink server
@music_plugin.listener(hikari.ShardReadyEvent)
async def start_lavalink(event: hikari.ShardReadyEvent) -> None:

    client = lavalink.Client(music_plugin.bot.get_me().id)

    client.add_node(
        host='localhost',
        port=2333,
        password=os.environ['LAVALINK_PASSWORD'],
        region='ru',
        name='default-node'
    )

    client.add_event_hooks(EventHandler())
    music_plugin.bot.d.lavalink = client

    youtube = build('youtube', 'v3', static_discovery=False, developerKey=os.environ["YOUTUBE_API_KEY"])
    music_plugin.bot.d.youtube = youtube
    music_plugin.bot.d.music = MusicCommand(music_plugin.bot)


@music_plugin.listener(hikari.VoiceServerUpdateEvent)
async def voice_server_update(event: hikari.VoiceServerUpdateEvent) -> None:

    lavalink_data = {
        't': 'VOICE_SERVER_UPDATE',
        'd': {
            'guild_id': event.guild_id,
            'endpoint': event.endpoint[6:],  # get rid of wss://
            'token': event.token,
        }
    }

    await music_plugin.bot.d.lavalink.voice_update_handler(lavalink_data)


@music_plugin.listener(hikari.VoiceStateUpdateEvent)
async def voice_state_update(event: hikari.VoiceStateUpdateEvent) -> None:

    prev_state = event.old_state
    cur_state = event.state

    # send event update to lavalink server
    lavalink_data = {
        't': 'VOICE_STATE_UPDATE',
        'd': {
            'guild_id': cur_state.guild_id,
            'user_id': cur_state.user_id,
            'channel_id': cur_state.channel_id,
            'session_id': cur_state.session_id,
        }
    }

    await music_plugin.bot.d.lavalink.voice_update_handler(lavalink_data)

    bot_id = music_plugin.bot.get_me().id
    bot_voice_state = music_plugin.bot.cache.get_voice_state(cur_state.guild_id, bot_id)

    if not bot_voice_state or cur_state.user_id == bot_id:
        return

    states = music_plugin.bot.cache.get_voice_states_view_for_guild(cur_state.guild_id).items()
    
    player = music_plugin.bot.d.lavalink.player_manager.get(cur_state.guild_id)
    # count users in channel with bot
    cnt_user = len([state[0] for state in filter(lambda i: i[1].channel_id == bot_voice_state.channel_id, states)])

    if cnt_user == 1:  # only bot left in voice
        await music_plugin.bot.d.music._leave(cur_state.guild_id)
        return
    if cnt_user > 2:  # not just bot & lone user -> resume player
        if player and player.paused:
            await player.set_pause(False)
        return
    
    # resume player when user undeafens
    if prev_state.is_self_deafened and not cur_state.is_self_deafened:
        if player and player.paused:
            await player.set_pause(False)
        else:
            return
        logging.info("Track resumed on guild: %s", event.guild_id)
    
    # pause player when user deafens
    if not prev_state.is_self_deafened and cur_state.is_self_deafened:
        if not player or not player.is_playing:
            return
        
        await player.set_pause(True)
        logging.info("Track paused on guild: %s", event.guild_id)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.option("запрос", "Название трека или ссылка на YouTube(Music)", required=True)
@lightbulb.option("повтор", "Включить повтор трека", choices=['да'], required=False, default=False)
@lightbulb.command("play", "Воспроизвести трек с YouTube по ссылке или названию", auto_defer = True)
@lightbulb.implements(lightbulb.SlashCommand)
async def play(ctx: lightbulb.SlashContext) -> None:
    """Searches the query on youtube, or adds the URL to the queue."""

    query = ctx.options['запрос']
    try:
        e = await music_plugin.bot.d.music._play(
            guild_id=ctx.guild_id,
            author_id=ctx.author.id,
            query=query,
            loop=(ctx.options['повтор'] == 'да')
        )
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("leave", "Отключить бота от голосового канала", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def leave(ctx: lightbulb.SlashContext) -> None:
    """Leaves the voice channel the bot is in, clearing the queue."""

    try:
        await music_plugin.bot.d.music._leave(ctx.guild_id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond("Выполнено отключение от голосового канала!")
        

@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("join", "Подключить бота к голосовому каналу, в котором вы находитесь", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def join(ctx: lightbulb.SlashContext) -> None:
    
    try:
        channel_id = await music_plugin.bot.d.music._join(ctx.guild_id, ctx.author.id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(f"Выполнено подключение к каналу <#{channel_id}>")


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("stop", "Останавливить воспроизведение текущего трека и очистить очередь", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def stop(ctx: lightbulb.SlashContext) -> None:
    """Stops the current song (skip to continue)."""

    try:
        e = await music_plugin.bot.d.music._stop(ctx.guild_id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("skip", "Пропустить текущий трек", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def skip(ctx: lightbulb.SlashContext) -> None:
    """Skips the current song."""

    try:
        e = await music_plugin.bot.d.music._skip(ctx.guild_id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("pause", "Приостановить текущий трек", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def pause(ctx: lightbulb.SlashContext) -> None:
    """Pauses the current song."""

    try:
        e = await music_plugin.bot.d.music._pause(ctx.guild_id, ctx.author.id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("resume", "Продолжить воспроизведение трека", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def resume(ctx: lightbulb.SlashContext) -> None:
    """Resumes playing the current song."""

    try:
        e = await music_plugin.bot.d.music._resume(ctx.guild_id, ctx.author.id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.option("время", "Временная отметка (формат: '[минуты]:[секунды]' )", required=True)
@lightbulb.command("seek", "Перемотать трек", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def seek(ctx : lightbulb.SlashContext) -> None:
    
    pos = ctx.options['время']
    try:
        e = await music_plugin.bot.d.music._seek(ctx.guild_id, pos)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("queue", "Показать следующие 10 треков в очереди", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def queue(ctx : lightbulb.SlashContext) -> None:
    
    try:
        e = await music_plugin.bot.d.music._queue(ctx.guild_id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.option("режим", "Режим повтора", choices=['трек', 'очередь', 'отмена'], required=False, default='трек')
@lightbulb.command("loop", "Повтор трека/очереди", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def loop(ctx : lightbulb.SlashContext) -> None:
    
    mode = ctx.options['режим']
    try:
        e = await music_plugin.bot.d.music._loop(ctx.guild_id, mode)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only, sr_check)
@lightbulb.command("shuffle", "Включить/выключить случайный порядок воспроизведения очереди", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def shuffle(ctx : lightbulb.SlashContext) -> None:
    
    try:
        e = await music_plugin.bot.d.music._shuffle(ctx.guild_id)
    except MusicCommandError as e:
        await ctx.respond(e)
    else:
        await ctx.respond(embed=e)


@music_plugin.command()
@lightbulb.option('запрос', 'Название трека или ссылка на YouTube(Music)', required=True)
@lightbulb.command('song_request', 'Заказ трека на стриме')
@lightbulb.implements(lightbulb.SlashCommand)
async def song_request(ctx: lightbulb.SlashContext) -> None:
    meta = youtube.get_request(ctx.options['запрос'])
    if meta:
        artists = ', '.join([artist['name'] for artist in meta['artists']])
        response = requests.post('http://localhost/api/sr/create', json = {
            'requested_by' : ctx.author.id,
            'title' : meta['title'],
            'artists' : artists,
            'url' : meta['url'],
        })
        if response.status_code == 200:
            data = response.json()
            embed = hikari.Embed(
                title = meta['title'],
                url = meta['url'],
                color = Color.from_hex_code("#FF0000")
            )
            embed.add_field('Продолжительность', meta['duration'])
            embed.add_field('Код трека', data['id'])
            embed.set_author(name=artists)
            embed.set_thumbnail(meta['thumbnail'])
            await ctx.respond(embed)
        elif response.status_code == 422:
            data = response.json()
            await ctx.respond(data['message'])
        else:
            await ctx.respond('Серверная ошибка.')
    else: ctx.respond('Ничего не найдено.')   


@music_plugin.command()
@lightbulb.option('код', 'Код трека для отмены заказа', required=True)
@lightbulb.command('song_remove', 'Отменить заказ трека')
@lightbulb.implements(lightbulb.SlashCommand)
async def song_remove(ctx: lightbulb.SlashContext) -> None:
    try:
        code = int(int(ctx.options['код']))
        user_roles = ctx.member.role_ids
        force = True if int(os.environ['ROLE_OWNER']) in user_roles or int(os.environ['ROLE_MOD']) in user_roles else False
        response = requests.post('http://localhost/api/sr/remove', json = {
            'track_id' : code,
            'discord_id' : ctx.author.id,
            'force' : force,
        })
        if response.status_code == 200:
            data = response.json()
            if int(data['deleted']) == 0:
                ctx.respond(':warning: Недостаточно прав для отмены заказа или трек отсутствует!')
            else:
                await ctx.respond(embed=hikari.Embed(description='Заказ трека отменен!', colour = 0x76ffa1))
        else:
            await ctx.respond('Серверная ошибка!')
    except:
        await ctx.respond(':warning: Ошибка! Код трека должен быть числом.')


@music_plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("режим", "Состояние плеера", choices=['on', 'off'], required=True)
@lightbulb.command("sr", "Треки сабов")
@lightbulb.implements(lightbulb.SlashCommand)
async def sr(ctx: lightbulb.SlashContext) -> None:
    if ctx.options['режим'] == 'on':
        music_plugin.bot.d.sr = True
        await ctx.respond(embed=hikari.Embed(description='Треки сабов включены!', colour = 0x76ffa1))
    else:
        music_plugin.bot.d.sr = False
        await ctx.respond(embed=hikari.Embed(description='Треки сабов отключены!', colour = 0x76ffa1))
        
async def ws_route_music(websocket, message):
    if message['command'] == 'subscribe':
        music_plugin.bot.d.music_subscribe_pool.add(websocket)
        
def init_ws_routes():
    if music_plugin.bot.get_plugin('websocket_server'):
        music_plugin.bot.d.music_subscribe_pool = set()
        music_plugin.bot.d.ws_routes['/music'] = ws_route_music

def load(bot: lightbulb.BotApp) -> None:

    bot.add_plugin(music_plugin)
    
    init_ws_routes()

    music_plugin.bot.d.sr = False

    @music_plugin.bot.listen(lightbulb.CommandErrorEvent)
    async def on_error(event: lightbulb.CommandErrorEvent) -> bool:
        if type(event.exception) is SongRequestsEnabledError:
            await event.context.respond(event.exception.args[0])
        return True