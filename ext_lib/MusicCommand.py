import re
import hikari
import logging

from ext_lib.utils import MusicCommandError
from ext_lib.logger import track_logger

class MusicCommand:
    
    def __init__(self, bot) -> None:
        self.bot = bot
    
    async def _join(self, guild_id, author_id):
        assert guild_id is not None

        states = self.bot.cache.get_voice_states_view_for_guild(guild_id)

        voice_state = [state[1] for state in filter(lambda i : i[0] == author_id, states.items())]
        bot_voice_state = [state[1] for state in filter(lambda i: i[0] == self.bot.get_me().id, states.items())]

        if not voice_state:
            raise MusicCommandError(":warning: Вы не подключены к голосовому каналу!")

        channel_id = voice_state[0].channel_id

        if bot_voice_state:
            if channel_id != bot_voice_state[0].channel_id:
                raise MusicCommandError(":warning: Бот уже используется в другом голосовом канале!")
        try:
            await self.bot.update_voice_state(guild_id, channel_id, self_deaf=True)
            self.bot.d.lavalink.player_manager.create(guild_id=guild_id)  
        except TimeoutError:
            raise MusicCommandError(":warning: Не получилось подключиться к голосовому каналу из-за ошибки или отсутствия прав!")
        
        logging.info("Client connected to voice channel on guild: %s", guild_id)
        return channel_id
    
    async def _play(self, guild_id, author_id, query: str, loop=False):
        assert guild_id is not None 

        query = query.strip('<>')
        player = self.bot.d.lavalink.player_manager.get(guild_id)

        if not player or not player.is_connected:
            await self._join(guild_id, author_id)
        
        player = self.bot.d.lavalink.player_manager.get(guild_id)

        url_rx = re.compile(r'https?://(?:www\.)?.+')
        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        if not results or not results.tracks:
            # return await ctx.respond(':warning: No result for query!')
            raise MusicCommandError(":warning: По данному запросу ничего не найдено!")
        
        embed = hikari.Embed(color=0x76ffa1)

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results.load_type == 'PLAYLIST_LOADED':
            tracks = results.tracks

            for track in tracks:
                # Add all of the tracks from the playlist to the queue.
                player.add(requester=author_id, track=track)
                track_logger.info("%s - %s (%s)", track.title, track.author, track.uri)

            embed.description = f"Плейлист '{results.playlist_info.name}' ({len(tracks)} добавлен в очередь [<@{author_id}>]"
        else:
            track = results.tracks[0]
            embed.description = f"Трек [{track.title}]({track.uri}) добавлен в очередь [<@{author_id}>]"

            player.add(requester=author_id, track=track)
            track_logger.info("%s - %s - %s", track.title, track.author, track.uri)

        if not player.is_playing:
            await player.play()
            if loop:
                player.set_loop(1) # 0 = off, 1 = track, 2 = queue
        else:
            logging.info("Track(s) enqueued on guild: %s", guild_id)
            if loop:
                raise MusicCommandError("Трек добавлен в очередь! Невозможно зациклить трек который находится в очереди!")
            
        return embed

    async def _leave(self, guild_id: str):

        player = self.bot.d.lavalink.player_manager.get(guild_id)

        if not player or not player.is_connected:
            raise MusicCommandError(":warning: Бот не подключен к голосовому каналу!")

        player.queue.clear()  # clear queue
        await player.stop()  # stop player
        await self.bot.update_voice_state(guild_id, None) # disconnect from voice channel
        
        logging.info("Bot disconnected from voice on guild: %s", guild_id)
    
    async def _stop(self, guild_id):

        player = self.bot.d.lavalink.player_manager.get(guild_id)
    
        if not player:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")
            
        player.queue.clear()
        await player.stop()

        logging.info("Player stopped on guild: %s", guild_id)

        return hikari.Embed(
            description = ":stop_button: Воспроизведение музыки остановлено!",
            colour = 0xd25557
        )
    
    async def _skip(self, guild_id):
        player = self.bot.d.lavalink.player_manager.get(guild_id)

        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")

        cur_track = player.current
        await player.play()

        logging.info("Track skipped on guild: %s", guild_id)

        return hikari.Embed(
            description = f":fast_forward: Пропущен трек: [{cur_track.title}]({cur_track.uri})",
            colour = 0xd25557
        )
    
    async def _pause(self, guild_id, author_id):
        assert guild_id is not None

        states = self.bot.cache.get_voice_states_view_for_guild(guild_id)

        voice_state = [state[1] for state in filter(lambda i : i[0] == author_id, states.items())]
        bot_voice_state = [state[1] for state in filter(lambda i: i[0] == self.bot.get_me().id, states.items())]
        
        if not voice_state:
            raise MusicCommandError(":warning: Вы не подключены к голосовому каналу!")

        channel_id = voice_state[0].channel_id

        if bot_voice_state:
            if channel_id != bot_voice_state[0].channel_id:
                raise MusicCommandError(":warning: Бот уже используется в другом голосовом канале!")
            
        player = self.bot.d.lavalink.player_manager.get(guild_id)

        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")
           
        await player.set_pause(True)

        logging.info("Track paused on guild: %s", guild_id)
        
        return hikari.Embed(
            description = ":pause_button: Воспроизведение приостановлено!",
            colour = 0xf9c62b
        )
    
    async def _resume(self, guild_id, author_id):
        assert guild_id is not None

        states = self.bot.cache.get_voice_states_view_for_guild(guild_id)

        voice_state = [state[1] for state in filter(lambda i : i[0] == author_id, states.items())]
        bot_voice_state = [state[1] for state in filter(lambda i: i[0] == self.bot.get_me().id, states.items())]
        
        if not voice_state:
            raise MusicCommandError(":warning: Вы не подключены к голосовому каналу!")

        channel_id = voice_state[0].channel_id

        if bot_voice_state:
            if channel_id != bot_voice_state[0].channel_id:
                raise MusicCommandError(":warning: Бот уже используется в другом голосовом канале!")
        
        player = self.bot.d.lavalink.player_manager.get(guild_id)
        
        if player and player.paused:
            await player.set_pause(False)
        else:
            raise MusicCommandError(":warning: Воспроизведение не приостановлено!")

        logging.info("Track resumed on guild: %s", guild_id)

        return hikari.Embed(
            description = ":arrow_forward: Воспроизведение возобновлено!",
            colour = 0x76ffa1
        )
    
    async def _seek(self, guild_id, pos):
        player = self.bot.d.lavalink.player_manager.get(guild_id)
        
        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")

        pos_rx = re.compile(r'\d+:\d{2}$')
        if not pos_rx.match(pos):
            raise MusicCommandError(":warning: Указано неверное время!")
        
        m, s = [int(x) for x in pos.split(':')]
        ms = m * 60 * 1000 + s * 1000
        await player.seek(ms)

        return hikari.Embed(
            description = f":fast_forward: Перемотка трека к отметке `{m}:{s:02}`!",
            colour = 0x76ffa1
        )
    
    async def _loop(self, guild_id, mode):
        player = self.bot.d.lavalink.player_manager.get(guild_id)
        
        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")
        
        body = ""
        if mode == 'отмена':
            player.set_loop(0)
            body = ":track_next: Повтор отключен!"
        if mode == 'трек':
            player.set_loop(1)
            body = f":repeat_one: Повтор трека включен!"
        if mode == 'очередь':
            player.set_loop(2)
            body = f":repeat: Повтор очереди включен!"
        
        return hikari.Embed(
            description = body,
            colour = 0xf0f8ff
        )
    
    async def _shuffle(self, guild_id):
        player = self.bot.d.lavalink.player_manager.get(guild_id)
        
        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")
        
        player.set_shuffle(not player.shuffle)

        return hikari.Embed(
            description = ":twisted_rightwards_arrows: " + ("Случайный порядок включен!" if player.shuffle else "Случайный порядок отключен!"),
            colour = 0xf0f8ff
        )
    
    async def _queue(self, guild_id):
        player = self.bot.d.lavalink.player_manager.get(guild_id)

        if not player or not player.is_playing:
            raise MusicCommandError(":warning: На данный момент ничего не играет!")

        emj = {
            player.LOOP_SINGLE: ':repeat_one:',
            player.LOOP_QUEUE: ':repeat:',
        }

        length = divmod(player.current.duration, 60000)
        queueDescription = f"**Текущий трек:** [{player.current.title}]({player.current.uri}) `{int(length[0])}:{round(length[1]/1000):02}` [<@!{player.current.requester}>]"
        i = 0
        while i < len(player.queue) and i < 10:
            if i == 0: 
                queueDescription += '\n\n' + '**Далее:**'
            length = divmod(player.queue[i].duration, 60000)
            queueDescription = queueDescription + '\n' + f"[{i + 1}. {player.queue[i].title}]({player.queue[i].uri}) `{int(length[0])}:{round(length[1]/1000):02}` [<@!{player.queue[i].requester}>]"
            i += 1

        return hikari.Embed(
            title = f":musical_note: Очередь {emj.get(player.loop, '')} \
                {':twisted_rightwards_arrows:' if player.shuffle else ''}",
            description = queueDescription,
            colour = 0x76ffa1,
        )