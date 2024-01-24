import asyncio 
import websockets
import json
import lightbulb

websocket_server = lightbulb.Plugin('websocket_server', 'This plugin provides a websocket server for the bot.')

async def ws_response(websocket, path):
    async for message in websocket:
        message = json.loads(message)
        await websocket_server.bot.d.ws_routes[path](websocket, message)

def load(bot: lightbulb.BotApp) -> None:
    
    bot.add_plugin(websocket_server)
    
    websocket_server.bot.d.ws_server = websockets.serve(ws_response, '0.0.0.0', '8000')
    websocket_server.bot.d.ws_routes = {}
    asyncio.get_event_loop().run_until_complete(websocket_server.bot.d.ws_server)