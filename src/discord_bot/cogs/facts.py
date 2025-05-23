import discord
from discord.ext import bridge, commands
import os


# https://guide.pycord.dev/popular-topics/cogs

class Fact(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(description='Test that the commands loaded') # Create prefixed command
    async def test4(self, ctx):
        await ctx.respond('testing worked! and updated')

    @discord.slash_command(description='Show how many matches total are tracked')
    async def match_count4(self, ctx):
        await ctx.defer() # Do this if query is slow

        try:
            count = await self.bot.pool.fetchval("SELECT COUNT(*) FROM matches")
            await ctx.respond(f"There have been {count} matches tracked so far!")
        except Exception as e:
            await ctx.respond(f"DB error")

def setup(bot):
    bot.add_cog(Fact(bot))