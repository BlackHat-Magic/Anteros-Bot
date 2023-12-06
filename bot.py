from dotenv import load_dotenv
from discord.ext import commands
from discord.ui import Button
from discord import ButtonStyle
import discord, os, re, requests, runpod, sys, time, asyncio

# set up stuff
load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API_KEY")
endpoint_id = os.getenv("RUNPOD_ENDPOINT")
endpoint = runpod.Endpoint(endpoint_id)
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
        self.convo = convo
        for item in self.children:
            item.callback = self.dispatch

    async def dispatch(self, interaction: discord.Interaction):
        custom_id = int(interaction.data["custom_id"])
        message = interaction.message

        await interaction.response.send_message("Editing now!", ephemeral=True, delete_after=30)

        request = endpoint.run({"messages": self.convo, "max_response_length": 256})

        response = await awaitResponse(request)
        response = response.replace("<|im_end|>", "")
        await message.edit(content=response, view=self)
    
async def awaitResponse(request):
    while(True):
        if(request.status() == "COMPLETED"):
            return(request.output())
        await asyncio.sleep(1)

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
    while len("".join(message_.content for message_ in messages)) > 4096:
        if(messages[0].content.startswith("# System Message\n\n") and messages[0].author == client.user):
           messages.pop[1]
           continue
        messages.pop(0)
    for message_ in messages:
        if(message_.id in searched_ids):
            continue
        searched_ids.append(message_.id)
        role = "user"
        content = message_.content
        if(content.startswith("# System Message\n\n") and message_.author == client.user):
            role = "system"
            content = content.replace("# System Message\n\n", "")
        elif(message_.author == client.user):
            role = "assistant"
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
    
    request = endpoint.run({"messages": convo, "max_response_length": 256})
    response = await awaitResponse(request)
    response = response.replace("<|im_end|>", "")
    await message.channel.send(response, view=view)

    if(not isinstance(message.channel, discord.Thread)):
        return
    if(message.channel.name != f"{client.user.name}: Thread" and not client.user.name in message.channel.name):
        return
    thread = message.channel

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
async def chat(interaction: discord.Interaction, system_prompt: str = None, start_message_bot: str = None):
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

    # assemble conversation
    if(system_prompt == None):
        system_prompt = "You are a helpful AI digital assistant chatting with a curious user. Answer their questions and fulfill their requests to the best of your abilities."
    
    convo = [{
        "role": "system",
        "content": system_prompt
    }]
    if(start_message_bot):
        convo.append({
            "role": "assistant",
            "content": start_message_bot
        })
    
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

    # set up initial context
    await thread.send(f"# System Message\n\n{system_prompt}")
    for message in convo:
        if(message["role"] != "assistant"):
            continue
        await thread.send(message["content"])


@client.tree.command(name="system")
async def chat(interaction: discord.Interaction, new_system_prompt: str):
    await interaction.response.send_message(f"# System Message\n\n{new_system_prompt}")

client.run(CLIENT_TOKEN)
