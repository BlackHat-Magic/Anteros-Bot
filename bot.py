from dotenv import load_dotenv
from discord.ext import commands
from openai import OpenAI
from chat_cog import ChatCog
import discord, os, re, asyncio, sys

from models import User, Request, create_database

# set up stuff
load_dotenv()
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT")
CLIENT_TOKEN = os.getenv("DISCORD_CLIENT_TOKEN")
CLIENT_ID = os.getenv("DISCORD_CLIENT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="c!", intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    endpoint = OpenAI(
        base_url=f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1",
        api_key=RUNPOD_API_KEY
    )
    try:
        session = create_database()
        self_user = session.get(User, client.user.id)
        if(not self_user):
            new_user = User(
                id=client.user.id,
                is_admin=True
            )
            session.add(new_user)
            session.commit()
        await client.add_cog(ChatCog(client, endpoint, session))
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)
        sys.exit()

client.run(CLIENT_TOKEN)
