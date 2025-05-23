import discord
from discord.ext import bridge, commands
import os


# https://guide.pycord.dev/popular-topics/cogs

class Deck(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(description='Test that the commands loaded') # Create prefixed command
    async def test2(self, ctx):
        await ctx.respond('testing worked! and updated')

def setup(bot):
    bot.add_cog(Deck(bot))