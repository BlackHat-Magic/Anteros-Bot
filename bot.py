from dotenv import load_dotenv
from discord.ext import commands
from discord.ui import Button
from discord import ButtonStyle
from openai import OpenAI
import discord, os, re, asyncio

# set up stuff
load_dotenv()
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT")
endpoint = OpenAI(
    base_url=f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1",
    api_key=RUNPOD_API_KEY
)
CLIENT_TOKEN = os.getenv("DISCORD_CLIENT_TOKEN")
CLIENT_ID = os.getenv("DISCORD_CLIENT_TOKEN")

# set up thread namer
thread_namer = ""
with open("system_prompt_thread.txt", "r") as f: thread_namer = f.read()

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="c!", intents=intents)

class MessageButtons(discord.ui.View):
    def __init__(self, convo):
        super().__init__()
        self.add_item(Button(style=ButtonStyle.primary, label="Redo", custom_id="0", row=0, emoji="↕"))
        self.add_item(Button(style=ButtonStyle.danger, label="Delete", custom_id="1", row=0, emoji="❌"))
        self.convo = convo
        self.children[0].callback = self.dispatch
        self.children[1].callback = self.delete

    async def dispatch(self, interaction: discord.Interaction):
        custom_id = int(interaction.data["custom_id"])
        message = interaction.message

        await interaction.response.send_message("Editing now!", ephemeral=True, delete_after=30)

        response = endpoint.chat.completions.create(
            model="TheDrummer/Gemmasutra-Mini-2B-v1",
            messages=convo
        )
        print(response)
        response = response.choices[0].message.content
        await message.edit(content=response, view=self)
    
    async def delete(self, interaction: discord.Interaction):
        await interaction.message.delete()
        await interaction.response.send_message("Message deleted.", ephemeral=True, delete_after=5)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)
        sys.exit()

@client.event
async def on_message(message):
    # check if invalid
    if(message.author == client.user or message.author.bot):
        return
    if(not isinstance(message.channel, discord.Thread) and not isinstance(message.channel, discord.DMChannel)):
        return
    if(not client.user.name in message.channel.name):
        return
    
    # assemble conversation
    messages = [message_ for message_ in reversed([message_ async for message_ in message.channel.history(limit=100)])]
    convo = []
    view = MessageButtons(convo)
    searched_ids = []
    while len("".join(message_.content for message_ in messages)) > 16384:
        messages.pop(0)
    for message_ in messages:
        if(message_.id in searched_ids):
            continue
        searched_ids.append(message_.id)
        content = message_.content
        if(len(content) < 1):
            continue
        if(message_.author == client.user):
            role = "assistant"
        else:
            role = "user"
        user_ids = re.findall("<@\d+>", content)
        for user_id in user_ids:
            uid = user_id.replace("<@", "").replace(">", "")
            user = await client.fetch_user(user_id)
            username = f"{user.name}#{user.discriminator}"
            if(user == client.user):
                username = client.user.name
            elif(user.discriminator == "0"):
                username = user.name
            content = content.replace(f"<@{userid}>", user.name)
        message_ = {
            "role": role,
            "content": content
        }
        convo.append(message_)
    
    response = endpoint.chat.completions.create(
        model="TheDrummer/Gemmasutra-Mini-2B-v1",
        messages=convo
    )
    response = response.choices[0].message.content

    split_response = response.split("\n")
    message_to_send = ""
    latest = None
    for i, paragraph in enumerate(split_response):
        if(len(paragraph) < 1):
            continue
        if(len(paragraph) > 2000):
            if(len(message_to_send) > 0):
                latest = await message.channel.send(message_to_send)
            message_to_send = ""
            sentences = paragraph.split(". ")
            paragraph_to_send = ""
            for j, sentence in enumerate(sentences):
                if(len(paragraph_to_send) + len(sentence) < 2000):
                    if(len(paragraph_to_send) > 0):
                        paragraph_to_send += ". "
                    paragraph_to_send += sentence
                else:
                    latest = await message.channel.send(paragraph_to_send, view=None)
                    paragraph_to_send = ""
            continue
        elif(len(message_to_send) + len(paragraph) < 1998):
            if(len(message_to_send) > 0):
                message_to_send += "\n\n"
            message_to_send += paragraph
            continue
        else:
            latest = await message.channel.send(message_to_send, view=None)
            message_to_send = ""
            continue
    
    latest_content = latest.content
    await latest.edit(content=latest_content, view=view)

    return

    # rename thread
    thread_convo = [
        {
            "role": "system",
            "content": thread_namer
        }
    ]
    for message in convo:
        thread_convo.append(message)
    
    thread_request = endpoint.run({"messages": thread_convo, "max_response_length": 256})
    response = await awaitResponse(thread_request)
    response = response.replace("<|im_end|>", "")
    await thread.edit(name=f"{client.user.name}: {response}"[:100])

@client.tree.command(name="chat")
async def chat(interaction: discord.Interaction):
    # check if it's a DM channel
    if(isinstance(interaction.channel, discord.DMChannel)):
        await interaction.response.send_message("You don't need to use /chat in DMs. Just send a message!\n\nTo change the system prompt, use `/system`.", ephemeral=True)
        return
    
    # check if it's already a thread
    if(isinstance(interaction.channel, discord.Thread)):
        await interaction.response.send_message("Conversation creation not supported in threads. If I created this thread, I will respond to messages automatically. Otherwise, use `/chat` in a normal channel to start a conversation.", ephemeral=True)
        return
    
    # check if it's a voice channel
    if(isinstance(interaction.channel, discord.VoiceChannel)):
        await interaction.response.send_message("Conversations not supported in voice channels.", ephemeral=True)
        return
    
    # get response
    await interaction.response.send_message("Creating thread...")
    await asyncio.sleep(0.100)
    confirmation_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

    # create thread
    thread = await confirmation_message.create_thread(
        name=f"{client.user.name}: Thread",
        auto_archive_duration=60,
        slowmode_delay=None,
        reason=None
    )

client.run(CLIENT_TOKEN)
