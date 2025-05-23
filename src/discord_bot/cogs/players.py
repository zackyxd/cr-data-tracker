import discord
from discord.ext import bridge, commands
import os

from discord_bot.utils.useful_embeds import not_in_database


# https://guide.pycord.dev/popular-topics/cogs

class Player(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    player = discord.SlashCommandGroup('player', 'Player related commands')

    # @discord.slash_command(description='Show how many matches total are tracked')
    @player.command()
    @discord.option('playertag', type=str, required=False)
    # @discord.option('user', type=discord.SlashCommandOptionType.user, required=False)
    async def matches(self, ctx, playertag):
        await ctx.defer() # Do this if query is slow

        if playertag and not playertag.startswith('#'):
            playertag = playertag.strip().upper()
            playertag = '#' + playertag
        try:
            playertag_exists = await self.bot.pool.fetchval(f"SELECT EXISTS "
                                                  f"(SELECT 1 FROM players WHERE playertag = $1)", playertag)
            if not playertag_exists:
                await ctx.respond(embed=not_in_database('playertag', playertag))
                return

            query = """
            SELECT
                p.player_name,
                COUNT(*) FILTER (WHERE TRUE) AS total,
                COUNT(*) FILTER (WHERE match_result = 'win') AS wins,
                COUNT(*) FILTER (WHERE match_result = 'loss') AS losses,
                COUNT(*) FILTER (WHERE match_result = 'throw') AS throws,
                COUNT(*) FILTER (WHERE match_result = 'tie') AS ties
            FROM matches m
            JOIN players p on m.playertag = p.playertag
            WHERE m.playertag = $1
            GROUP BY p.player_name
            """
            row = await self.bot.pool.fetchrow(query, playertag)
            total_matches = row["total"]
            wins = row["wins"]
            losses = row["losses"]
            throws = row["throws"]
            ties = row["ties"]
            name = row["player_name"]
            if wins + losses == 0:
                win_rate = 0
            else:
                win_rate = (wins / (wins+losses)) * 100
            print(total_matches, losses, throws, ties, name)

            embed = discord.Embed(
                title=f'All Matches for {name}',
                color=discord.Color.dark_blue(),
            )
            embed.set_footer(text=playertag)
            embed.set_thumbnail(url=os.getenv('BOT_IMAGE'))

            embed.add_field(name='Matches', value=total_matches)
            embed.add_field(name='Wins', value=wins, inline=True)
            embed.add_field(name='Losses', value=losses, inline=True)
            embed.add_field(name='Win Rate', value=f'{win_rate:.2f}%', inline=True)
            embed.add_field(name='Throws', value=throws)
            embed.add_field(name='Ties', value=ties)


            await ctx.respond(embed=embed)
        except Exception as e:
            print(e)
            await ctx.respond(f"DB error")

def setup(bot):
    bot.add_cog(Player(bot))