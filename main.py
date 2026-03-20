import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from game_session import GameSession

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store active game sessions per channel
active_sessions = {}


class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is alive!')

    def log_message(self, format, *args):
        pass


def run_keep_alive():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    print(f'Keep-alive server running on port {port}')
    server.serve_forever()


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to run "This or That" compatibility games!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="start", description="Start a new This or That compatibility game")
async def start_game(interaction: discord.Interaction):
    """Start a new This or That compatibility game"""
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
        print(f"Error in game session: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred during the game. Please try again.")
        else:
            await interaction.followup.send("❌ An error occurred during the game. Please try again.")
    finally:
        if channel_id in active_sessions:
            del active_sessions[channel_id]

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing your command.")

@bot.event
async def on_error(event, *args, **kwargs):
    """Handle general bot errors"""
    print(f"Bot error in {event}: {args}")

# Run the bot
if __name__ == "__main__":
    token = os.environ.get('TOKEN')
    if not token:
        print("❌ Error: Discord bot token not found in environment variables!")
        print("Please set the TOKEN environment variable in Render environment settings.")
        exit(1)

    keep_alive_thread = threading.Thread(target=run_keep_alive, daemon=True)
    keep_alive_thread.start()

    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Error: Invalid Discord bot token!")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
