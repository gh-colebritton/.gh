import servicemanager
import win32serviceutil
import win32service
import win32event
import threading
import asyncio
import discord
import pyodbc
from datetime import datetime
from zoneinfo import ZoneInfo
import aiohttp
import os

# this python script forwards discord messages to a local SQL server to save and query messages within a specific text channel.
# this utilized an api token from the bot and a webhook to push and pull data respectively.
# interest for this project came from a need for testing data for sql.
 
DISCORD_BOT_TOKEN = 'os.getenv("API_TOKEN)'

if not DISCORD_BOT_TOKEN:
    raise ValueError("API_TOKEN environment variable not set")

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=192.168.1.179,1433;"
    "DATABASE=DiscordArchive;"
    "UID=discordbot;"
    "PWD=Administrator;"
    "TrustServerCertificate=yes;"
)

AUTHORIZED_USERS = {129413794660089869, 129637129465757696, 279064977044930571}

EST = ZoneInfo("America/New_York")
intents = discord.Intents.default()
intents.message_content = True

WEBHOOK_URL = 'os.getenv("WEBHOOK_URL")'
    
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable not set")

client = discord.Client(intents=intents)

def save_message_to_db(message):
    timestamp_est = message.created_at.astimezone(EST)
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM DiscordMessages WHERE MessageID = ?)
                INSERT INTO DiscordMessages
                (MessageID, GuildID, GuildName, ChannelID, ChannelName, AuthorID, AuthorName, Content, Timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.id,
                message.guild.id if message.guild else None,
                message.guild.name if message.guild else None,
                message.channel.id,
                message.channel.name,
                message.author.id,
                message.author.name,
                message.content,
                timestamp_est
            ))
            conn.commit()
            servicemanager.LogInfoMsg(f"Saved message {message.id} from {message.author}")
    except Exception as e:
        servicemanager.LogErrorMsg(f"Error saving message {message.id}: {e}")

def run_sql_query(sql: str):
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchmany(5)
                results = [dict(zip(columns, row)) for row in rows]
                return results
            else:
                conn.commit()
                return []
    except Exception as e:
        return f"SQL Error: {e}"

async def send_webhook_message(content):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
        await webhook.send(content)

@client.event
async def on_ready():
    servicemanager.LogInfoMsg(f'Logged in as {client.user} - Bot is ready!')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Shutdown command
    if message.content.strip() == "!shutdown" and message.author.id in AUTHORIZED_USERS:
        await send_webhook_message(f"<@{message.author.id}> Bot was shut down via Discord.")
        await client.close()
        return

    save_message_to_db(message)

    if message.content.startswith("\\"):
        if message.author.id not in AUTHORIZED_USERS:
            await message.channel.send("You are not authorized to run SQL queries.")
            return

        sql = message.content[1:].strip()
        result = run_sql_query(sql)

        if isinstance(result, str):
            await message.channel.send(result)
        elif result:
            response_lines = ["```"]
            for row in result:
                response_lines.append(" | ".join(f"{k}: {v}" for k, v in row.items()))
            response_lines.append("```")
            await message.channel.send("\n".join(response_lines))
        else:
            await message.channel.send("Query ran successfully, but no rows returned.")

@client.event
async def on_disconnect():
    servicemanager.LogInfoMsg("Bot disconnected, sending webhook notification...")
    try:
        await send_webhook_message("BreadsticksBot has disconnected or gone offline.")
    except Exception as e:
        servicemanager.LogErrorMsg(f"Failed to send webhook notification on disconnect: {e}")

async def start_bot():
    await client.start(DISCORD_BOT_TOKEN)

def run_bot(stop_event):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(start_bot())
    try:
        while not stop_event.is_set():
            loop.run_until_complete(asyncio.sleep(1))
    except Exception:
        pass
    finally:
        loop.run_until_complete(client.close())
        loop.close()

class DiscordBotService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DiscordBotService"
    _svc_display_name_ = "Discord Bot Service"
    _svc_description_ = "Runs the Discord bot as a Windows Service."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.stop_event = threading.Event()
        self.bot_thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        servicemanager.LogInfoMsg("Service stop requested")
        self.stop_event.set()
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=15)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Service is starting...")
        self.bot_thread = threading.Thread(target=run_bot, args=(self.stop_event,))
        self.bot_thread.start()
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        servicemanager.LogInfoMsg("Service stopped.")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(DiscordBotService)