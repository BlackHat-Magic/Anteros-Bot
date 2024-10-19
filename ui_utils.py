from discord.ui import Button, View, TextInput, Modal
from discord import ButtonStyle, Interaction, utils
from models import Message, Variant
import discord

class MessageButtons(View):
    def __init__(self, prev_button, next_button):
        super().__init__()
        self.add_item(Button(style=ButtonStyle.primary, label="Redo", custom_id="0", row=0, emoji="🔄"))
        self.add_item(Button(style=ButtonStyle.danger, label="Delete", custom_id="1", row=1, emoji="❌"))
        if(prev_button):
            self.add_item(Button(style=ButtonStyle.primary, label="Previous Response", custom_id="2", row=0, emoji="⬅️"))
        if(next_button):
            self.add_item(Button(style=ButtonStyle.primary, label="Next Response", custom_id="3", row=0, emoji="➡️"))
        # self.add_item(Button(style=ButtonStyle.primary, label="Edit", custom_id="4", row=2, emoji="✒️"))
    
# class EditorModal(Modal, text="", session=None, db_message_id=0, client=None, title="Edit Message"):
#     self.text = TextInput(
#         label="Message Text", 
#         default=text,
#         placeholder="Message Text",
#         required=True,
#         min_length=1,
#         max_length=4000,
#         style=discord.TextStyle.paragraph
#     )
#     self.title = "Edit Message"
#     self.custom_id="-1"
#     self.session = session
#     self.db_message_id = db_message_id
#     self.client = client
#     async def on_submit(self, interaction: discord.Interaction):
#         # get the database message, variant
#         db_message = self.session.query(Message).filter_by(discord_id=db_message_id).first()
#         selected_variant = db_message.selected_variant
#         all_variants = self.session.query(Variant).filter_by(messageid=db_message_id).all()
#         selected_variant = all_variants[selected_variant]

#         # delete the old message
#         messages = await interaction.channel.history(limit=100)
#         while(messages[0].id != db_message_id):
#             messages.pop(0)
#         while(messages[0].author == self.client.user):
#             await messages[0].delete()
#             messages.pop(0)
        
#         # write the new message
#         split_content = [self.text[i:i+1900] for i in range(0, len(self.text), 1900)]
#         for chunk in split_content:
#             latest = await message.channel.send(chunk)
#         view = MessageButtons(selected_variant > 0, selected_variant < len(all_variants) - 1)

#         selected_variant.text = self.text
#         db_message.discord_id = latest.id
#         self.session.commit()
        