import discord
from discord.ext import commands
import os
import asyncio
import threading
import random
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler
from game_session import GameSession

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

# Dictionary to store active game sessions per channel
active_sessions = {}

PORT = int(os.environ.get('PORT', 10000))


class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is alive!')

    def log_message(self, format, *args):
        pass


def run_keep_alive():
    server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
    print(f'Keep-alive server running on port {PORT}')
    server.serve_forever()


async def self_ping_loop():
    """Ping own HTTP server every 10 minutes to prevent Render from sleeping."""
    await asyncio.sleep(60)
    url = os.environ.get('RENDER_URL') or f'http://localhost:{PORT}'
    print(f'Self-ping active: pinging {url} every 10 minutes.')
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    print(f'Self-ping OK ({resp.status})')
            except Exception as e:
                print(f'Self-ping failed: {e}')
            await asyncio.sleep(600)


def make_bot():
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        print(f'{bot.user} has connected to Discord!')
        print('Bot is ready to run "This or That" compatibility games!')
        try:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} command(s)')
        except Exception as e:
            print(f'Failed to sync commands: {e}')
        bot.loop.create_task(self_ping_loop())

    @bot.tree.command(name="start", description="Start a new This or That compatibility game")
    async def start_game(interaction: discord.Interaction):
        channel_id = interaction.channel.id

        if channel_id in active_sessions:
            await interaction.response.send_message("❌ There's already an active game in this channel! Please wait for it to finish.")
            return

        session = GameSession(interaction, bot)
        active_sessions[channel_id] = session

        try:
            await interaction.response.defer()
            await session.start_game()
        except Exception as e:
            print(f'Error in game session: {e}')
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred during the game. Please try again.")
            else:
                await interaction.followup.send("❌ An error occurred during the game. Please try again.")
        finally:
            if channel_id in active_sessions:
                del active_sessions[channel_id]

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f'Command error: {error}')
        await ctx.send("❌ An error occurred while processing your command.")

    @bot.event
    async def on_error(event, *args, **kwargs):
        print(f'Bot error in {event}: {args}')

    return bot


async def run_bot_with_retry(token):
    max_retries = 50
    base_delay = 30

    # Random startup delay to avoid hitting rate limits when Render restarts
    startup_delay = random.randint(5, 20)
    print(f'Startup delay: {startup_delay}s (avoids rate limiting)...')
    await asyncio.sleep(startup_delay)

    attempt = 0
    while True:
        attempt += 1
        bot = make_bot()
        try:
            print(f'Connecting to Discord... (attempt {attempt})')
            await bot.start(token)
        except discord.LoginFailure:
            print('❌ Error: Invalid Discord bot token! Stopping.')
            break
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'rate limit' in error_str.lower() or '1015' in error_str:
                wait = min(base_delay * attempt, 300)
                print(f'⚠️ Rate limited (attempt {attempt}). Retrying in {wait}s...')
            else:
                wait = base_delay
                print(f'⚠️ Connection lost: {e}. Reconnecting in {wait}s...')
            await asyncio.sleep(wait)
        finally:
            try:
                if not bot.is_closed():
                    await bot.close()
            except Exception:
                pass


if __name__ == "__main__":
    token = os.environ.get('TOKEN')
    if not token:
        print('❌ Error: TOKEN environment variable not set!')
        exit(1)

    keep_alive_thread = threading.Thread(target=run_keep_alive, daemon=True)
    keep_alive_thread.start()

    asyncio.run(run_bot_with_retry(token))
