from dotenv import load_dotenv
from discord.ext import commands
from openai import OpenAI
from chat_cog import ChatCog
import discord
import os
import sys

from models import User, create_database

# set up stuff
load_dotenv()

RUNPOD_API_KEY: str = os.getenv("RUNPOD_API_KEY", "")
if not RUNPOD_API_KEY:
    raise ValueError("RUNPOD_API_KEY cannot be None")

RUNPOD_ENDPOINT_ID: str = os.getenv("RUNPOD_ENDPOINT", "")
if not RUNPOD_ENDPOINT_ID:
    raise ValueError("RUNPOD_ENDPOINT_ID cannot be None")

CLIENT_TOKEN: str = os.getenv("DISCORD_CLIENT_TOKEN", "")
if not CLIENT_TOKEN:
    raise ValueError("DISCORD_CLIENT_TOKEN cannot be None")

CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID") or ""
if not CLIENT_ID:
    raise ValueError("DISCORD_CLIENT_ID cannot be None")

intents: discord.Intents = discord.Intents.default()
intents.message_content = True
client: commands.Bot = commands.Bot(command_prefix="c!", intents=intents)


@client.event
async def on_ready() -> None:
    print(f"Logged in as {client.user}.")
    endpoint = OpenAI(
        base_url=f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1",
        api_key=RUNPOD_API_KEY,
    )
    session = create_database()  # TODO

    if client.user is None:
        raise Exception
    self_user: User | None = session.get(User, client.user.id)
    if not self_user:
        new_user: User = User(id=client.user.id, is_admin=True)
        session.add(new_user)
        session.commit()

    await client.add_cog(ChatCog(client, endpoint, session))
    synced = await client.tree.sync()  # TODO
    print(f"Synced {len(synced)} command(s).")


if __name__ == "__main__":
    client.run(CLIENT_TOKEN)
