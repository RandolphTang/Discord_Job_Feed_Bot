from datetime import datetime
import os
import discord
from discord.ext import commands, tasks
import json
from dotenv import load_dotenv
from job_scraper_bot import scrape_github_internships, sort_dataframe_by_date

# load_dotenv()

bot_token = os.getenv('DISCORD_TOKEN')


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(object)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!', intents=intents)

url = "https://github.com/SimplifyJobs/Summer2025-Internships"


def load_channel_config():
    try:
        with open("channel_config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_channel_config(config):
    with open("channel_config.json", "w") as f:
        json.dump(config, f, indent=2)


channel_config = load_channel_config()


def load_internships():
    try:
        with open("internships.json", "r") as f:
            internships = json.load(f)
        for internship in internships:
            if 'Date Posted' in internships:
                internship['Date Posted'] = datetime.fromisoformat(internship['Date Posted'])
        return internships
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_internships(internships):
    with open("internships.json", "w") as f:
        json.dump(internships, f, indent=2, cls=DateTimeEncoder)


async def fetch_internships():
    try:
        df = await scrape_github_internships(url)
        df_sorted = sort_dataframe_by_date(df)
        return df_sorted.to_dict('records')
    except Exception as e:
        print(f"Error in fetch_internships: {str(e)}")
        return []


# async def update_internships_for_guild(guild_id):
#     try:
#         new_internships = await fetch_internships()
#         old_internships = load_internships()
#         new_entries = [i for i in new_internships if i not in old_internships]
#
#         if new_entries and guild_id in channel_config:
#             channel_id = channel_config[guild_id]
#             channel = bot.get_channel(int(channel_id))
#             if channel:
#                 for internship in new_entries:
#                     embed = discord.Embed(title=f"**__```{internship['Company']} - {internship['Role']}```__**",
#                                           color=0x00ff00)
#                     embed.add_field(name="🌍 Location", value=internship['Location'], inline=True)
#
#                     date_posted = internship['Date Posted']
#                     if isinstance(date_posted, datetime):
#                         date_posted = date_posted.strftime('%b %d')
#
#                     embed.add_field(name="📅 Date Posted", value=date_posted, inline=True)
#                     embed.add_field(name="💼 Application Link", value=internship['Application/Link'],
#                                     inline=False)
#                     await channel.send(embed=embed)
#
#         save_internships(new_internships)
#
#     except Exception as e:
#         print(f"An error occurred updating for guild {guild_id}: {str(e)}")

@tasks.loop(hours=0.5)
async def update_internships():
    new_internships = await fetch_internships()
    for channel_id, config in channel_config.items():
        channel = bot.get_channel(int(channel_id))
        if channel:
            last_update = datetime.fromisoformat(config["last_update"]) if config["last_update"] else None
            new_entries = [i for i in new_internships if
                           not last_update or datetime.fromisoformat(i['Date Posted']) > last_update]
            for internship in new_entries:
                embed = create_internship_embed(internship)
                await channel.send(embed=embed)
            if new_entries:
                channel_config[channel_id]["last_update"] = datetime.now().isoformat()
                save_channel_config(channel_config)


def create_internship_embed(internship):
    embed = discord.Embed(title=f"**__```{internship['Company']} - {internship['Role']}```__**", color=0x00ff00)
    embed.add_field(name="🌍 Location", value=internship['Location'], inline=True)
    embed.add_field(name="📅 Date Posted", value=internship['Date Posted'], inline=True)
    embed.add_field(name="💼 Application Link", value=internship['Application/Link'], inline=False)
    return embed


@bot.event
async def on_ready():
    print(f'{bot.user} reports on duty!')
    update_internships.start()


@bot.event
async def on_guild_join(guild):
    general = discord.utils.find(lambda x: x.name == 'general', guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        await general.send(
            "Meow! I'm the Job_Feed_Kitten. Admin can use `!set_channel` in the channel where you want me to report"
            "internship updates.")


@bot.command()
async def set_channel(ctx):
    channel_config[ctx.channel.id] = {"last_update": None}
    save_channel_config(channel_config)
    await ctx.send("Internship updates will now be sent to this channel, Meow!.")
    await send_initial_internships(ctx.channel)


async def send_initial_internships(channel):
    internships = await fetch_internships()
    for internship in internships:
        embed = create_internship_embed(internship)
        await channel.send(embed=embed)
    channel_config[channel.id]["last_update"] = datetime.now().isoformat()
    save_channel_config(channel_config)


bot.run(bot_token)
