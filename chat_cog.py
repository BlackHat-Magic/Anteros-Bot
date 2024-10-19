from discord import app_commands
from discord.ext import commands
from ui_utils import MessageButtons#, EditorModal
from dotenv import load_dotenv
from models import User, Channel, Message, Variant, Request
import discord, openai, asyncio, os, re, time

async def assemble_conversation(channel, client):
    messages = [message for message in reversed([message async for message in channel.history(limit=100)])]
    convo = []
    searched_ids = []
    while len("".join(message.content for message in messages)) > 16384:
        messages.pop(0)

    # loop through messages
    for message in messages:
        # delete "too many request" messages.
        if("Too many requests (limit 100 per hour)." in message.content and message.author == client.user):
            await message.delete()
            continue
        
        # tbh idk why this is here
        if(message.id in searched_ids):
            continue
        searched_ids.append(message.id)

        # clean up message metadata
        content = message.content
        if(len(content) < 1):
            continue
        if(message.author == client.user):
            role = "assistant"
        elif(message.author.bot):
            continue
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
        
        # fix some stuff about the message.
        if(len(convo) > 0 and convo[-1]["role"] == role):
            convo[-1]["content"] += content
        else:
            message = {
                "role": role,
                "content": content
            }
            convo.append(message)
    return(convo)

class ChatCog(commands.Cog):
    def __init__(self, client, endpoint, session):
        self.client = client
        self.endpoint = endpoint
        self.user_limits = {}
        self.session = session
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        # Get the custom ID
        custom_id = interaction.data.get("custom_id", None)
        if(not custom_id):
            return
        
        # get the message
        message = interaction.message
        db_message = self.session.query(Message).filter_by(discord_id=message.id).first()
        if(not db_message):
            await interaction.response.send_message("Error; Couldn't find message.", ephemeral=True)
            return

        # get channe;
        channel = interaction.channel
        db_channel = self.session.get(Channel, channel.id)
        if(not db_channel):
            await interaction.response.send_message("Error; Couldn't find thread.", ephemeral=True)

        # if this isn't the user that requested the message, they can't change it
        db_user = self.session.get(User, interaction.user.id)
        if(not db_user):
            await interaction.response.send_message("Only the channel creator can change the thread.", ephemeral=True)
            return
        if(db_user.id != db_channel.user.id):
            print(db_user.id)
            print(db_channel.user.id)
            await interaction.response.send_message("Only the channel creator can change the thread.", ephemeral=True)
            return

        # redo message
        if(custom_id == "0"):
            await interaction.response.defer()
            view = MessageButtons(True, False)
            # setup editing
            if(not db_message):
                await interaction.followup.send("Error; message could not be found.", ephemeral=True)
                return
            interim = await interaction.followup.send("Editing now!", ephemeral=True)

            # remove old message
            messages = [message for message in reversed([message async for message in channel.history(limit=100)])]
            while messages[-1].id != db_message.discord_id:
                await messages[-1].delete()
                messages.pop()
            while messages[-1].author == self.client.user:
                await messages[-1].delete()
                messages.pop()
            
            # generate a new message
            convo = await assemble_conversation(channel, self.client)
            response = self.endpoint.chat.completions.create(
                model="TheDrummer/Gemmasutra-Mini-2B-v1",
                messages=convo
            )
            response = response.choices[0].message.content
            split_response = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for chunk in split_response:
                latest = await channel.send(chunk.replace("<end_of_turn>", ""))
            await latest.edit(view=view)
            await interim.delete()

            # log new variant in database
            now = time.time()
            db_message.discord_id = latest.id
            db_message.selected_variant = self.session.query(Variant).filter_by(messageid=db_message.id).count()
            new_variant = Variant(
                message=db_message,
                text=response
            )
            new_request = Request(
                user=db_user
            )
            self.session.add(new_variant)
            self.session.add(new_request)
            self.session.commit()

        if(custom_id == "1"):
            await interaction.response.defer()
            await message.delete()
            message_variants = self.session.query(Variant).filter_by(messageid=db_message.id).all()
            for variant in message_variants:
                self.session.delete(variant)
            self.session.delete(db_message)
            self.session.commit()
        
        if(custom_id == "2"):
            await interaction.response.defer()
            if(db_message.selected_variant < 1):
                await interaction.followup.send("How did you do that?", ephemeral=True)
                return
            messages = [message for message in reversed([message async for message in channel.history(limit=100)])]
            while messages[-1].id != db_message.discord_id:
                await messages[-1].delete()
                messages.pop()
            while messages[-1].author == self.client.user:
                await messages[-1].delete()
                messages.pop()

            target_variant = db_message.selected_variant - 1
            content = self.session.query(Variant).filter_by(messageid=db_message.id).all()[target_variant].text
            split_content = [content[i:i+1900] for i in range(0, len(content), 1900)]
            for chunk in split_content:
                latest = await message.channel.send(chunk.replace("<end_of_turn>", ""))
            view = MessageButtons(target_variant > 0, True)
            await latest.edit(view=view)
            db_message.discord_id = latest.id
            db_message.selected_variant -= 1
            self.session.commit()
        
        if(custom_id == "3"):
            await interaction.response.defer()
            possible_variants = self.session.query(Variant).filter_by(messageid=db_message.id).all()
            if(db_message.selected_variant >= len(possible_variants)):
                await interaction.followup.send("How did you do that?", ephemeral=True)
                return
            messages = [message for message in reversed([message async for message in channel.history(limit=100)])]
            while messages[-1].id != db_message.discord_id:
                await messages[-1].delete()
                messages.pop()
            while messages[-1].author == self.client.user:
                await messages[-1].delete()
                messages.pop()

            target_variant = db_message.selected_variant + 1
            content = possible_variants[target_variant].text
            split_content = [content[i:i+1900] for i in range(0, len(content), 1900)]
            for chunk in split_content:
                latest = await message.channel.send(chunk.replace("<end_of_turn>", ""))
            view = MessageButtons(True, target_variant < len(possible_variants) - 1)
            await latest.edit(view=view)
            db_message.discord_id = latest.id
            db_message.selected_variant += 1
            self.session.commit()

        if(custom_id == "4"):
            all_variants = self.session.query(Variant).filter_by(messageid=db_message.id).all()
            variant = all_variants[db_message.selected_variant]
            await interaction.response.send_modal(EditorModal(
                text=variant.text,
                session=self.session,
                db_message_id=db_message.discord_id,
                client=self.client
            ))

    @commands.Cog.listener()
    async def on_message(self, message):
        # check if invalid
        if(message.author == self.client.user or message.author.bot):
            return
        if(not isinstance(message.channel, discord.Thread) and not isinstance(message.channel, discord.DMChannel)):
            return
        if(not f"{self.client.user.name}: " in message.channel.name):
            return
        
        # check if user exits
        db_user = self.session.get(User, message.author.id)
        if(not db_user):
            db_user = User(
                id=message.author.id,
            )
            self.session.add(db_user)
            self.session.commit()
        userid = db_user.id

        # check if thread exists
        db_thread = self.session.get(Channel, message.channel.id)
        if(not db_thread):
            if(not isinstance(message.channel, discord.DMChannel)):
                return
            else:
                db_thread = Channel(
                    id=message.channel,
                    user=db_user,
                )
                self.session.add(db_thread)
                self.session.commit()
        
        # check if user exceeds 100 requests/hour
        user_requests = self.session.query(Request).filter_by(userid=userid).all()
        user_requests.sort(key=lambda x: x.date if x.date else 0)
        now = time.time()
        if(len(user_requests) > 100):
            while user_requests[0].date < now - 3600:
                self.session.delete(user_requests[0])
                user_requests.pop(0)
        self.session.commit()
        if(len(user_requests) >= 100):
            earliest_request = user_requests[0]
            message.channel.send(f"Too many requests (limit 100 per hour).\n\nTry again at {int(now) + 3600}.\n\n-# This message will delete itself next time you make a valid request.", delete_after=60)
            return
        
        # get conversation
        convo = await assemble_conversation(message.channel, self.client)
        view = MessageButtons(False, False)
        
        # get and send the response
        response = self.endpoint.chat.completions.create(
            model="TheDrummer/Gemmasutra-Mini-2B-v1",
            messages=convo
        )
        response = response.choices[0].message.content
        split_response = [response[i:i+1900] for i in range(0, len(response), 1900)]
        for chunk in split_response:
            latest = await message.channel.send(chunk.replace("<end_of_turn>", ""))
        await latest.edit(view=view)

        # log the response in the database
        now = time.time()
        new_message = Message(
            discord_id=latest.id,
            channel=db_thread,
            user=db_user,
            selected_variant=0,
        )
        new_variant = Variant(
            message=new_message,
            text=response
        )
        new_request = Request(
            user=db_user,
            date=now
        )
        self.session.add(new_message)
        self.session.add(new_variant)
        self.session.add(new_request)
        self.session.commit()
        return

        # split respo
        split_response = response.split("\n")
        message_to_send = ""
        latest = None
        for i, paragraph in enumerate(split_response):
            if(len(paragraph) < 1):
                continue
            if(len(paragraph) > 2000):
                if(len(message_to_send) > 0):
                    message_to_send += ". "
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
        
        thread_request = self.endpoint.run({"messages": thread_convo, "max_response_length": 256})
        response = await awaitResponse(thread_request)
        response = response.replace("<|im_end|>", "")
        await thread.edit(name=f"{self.client.user.name}: {response}"[:100])

    @app_commands.command(name="chat")
    async def chat(self, interaction: discord.Interaction):
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
        
        # get user
        db_user = self.session.get(User, interaction.user.id)
        if(not db_user):
            db_user = User(
                id=interaction.user.id
            )
            self.session.add(db_user)
        
        # get response
        await interaction.response.send_message("Creating thread...")
        await asyncio.sleep(0.100)
        confirmation_message = await interaction.channel.fetch_message(interaction.channel.last_message_id)

        # create thread
        thread = await confirmation_message.create_thread(
            name=f"{self.client.user.name}: Thread",
            auto_archive_duration=60,
            slowmode_delay=None,
            reason=None
        )

        new_channel = Channel(
            id=thread.id,
            user=db_user
        )
        self.session.add(new_channel)
        self.session.commit()