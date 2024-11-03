# -*- coding: utf-8 -*-
import discord
import os
import json
import csv
import schedule
import pytz
import threading
import asyncio
from dotenv import load_dotenv
from time import sleep
from datetime import datetime
from discord import app_commands
load_dotenv('discord bot tokenがある.envを指定（直書きなら消してね）')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
client = discord.Client(intents=intents, activity=discord.Game("出席確認中"))
tree = app_commands.CommandTree(client)
schedule_time = "09:30"

TOKEN = os.getenv('Token')
CHANNEL_ID = 定期投稿するchannel id
ALLOWED_USER_ID = 使う人のuser id
JSON_FILE_PATH = 'script/info.json'
CSV_FILE_PATH = 'script/年間予定.csv'

def load_attendance_data():
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, 'r') as f:
            return json.load(f)
    else:
        return {"attendance": 0, "absence": 0}

def save_attendance_data(data):
    with open(JSON_FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def is_school_day():
    today = datetime.now().strftime("%-m-%-d")
    with open(CSV_FILE_PATH, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.reader(csv_file)
        for row in csv_reader:
            if (len(row) > 3) and (row[0] + "-" + row[1] == today) and ("休校日" in row[3] or "自由登校" in row[3]): return False
    return True

def get_school_days():
    holiday_count = 0
    free_attendance_count = 0
    start_date = datetime(2024, 4, 1)
    end_date = datetime(2025, 3, 31)
    total_days = (end_date - start_date).days + 1

    with open(CSV_FILE_PATH, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.reader(csv_file)
        print(csv_reader)
        for row in csv_reader:
            if len(row) > 3:
                if "休校日" in row[3]:
                    holiday_count += 1
                if "自由登校" in row[3]:
                    free_attendance_count += 1
    total_non_school_days = holiday_count + free_attendance_count
    return total_days - total_non_school_days

async def check_and_notify():
    if is_school_day():
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await send_to_discord("n今日は出席日です。\n出席しましたか？遅刻または欠席ですか？")
            print(f"今日は出席日です。\n日付 : {datetime.now()}")
    else:
        print(f"今日は休校日または自由登校日です。\n日付 : {datetime.now()}")

def aggregate_attendance_data(data):
    attendance_count = data['attendance']
    absence_count = data['absence']
    total_days = attendance_count + absence_count
    school_days = get_school_days()
    remaining_school_days = school_days - total_days
    attendance_ratio = (attendance_count / total_days) * 100 if total_days > 0 else 0
    required_attendance = int(school_days * 0.8)
    remaining_days_for_pass = max(0, required_attendance - attendance_count)
    late_allowed_count = remaining_school_days - remaining_days_for_pass

    return attendance_count, absence_count, attendance_ratio, remaining_days_for_pass, school_days, remaining_school_days, late_allowed_count

def get_japan_time():
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst)

@client.event
async def on_ready():
    await tree.sync()
    print(f'┎-------------------------------┒\n┃login is successful            ┃\n┃logged in {client.user}     ┃\n┖-------------------------------┚')

@tree.command(name="schoolday", description="手動で登校日のメッセージを出力します。")
async def schoolday_command(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)
        return

    await send_to_discord("今日は出席日です。\n出席しましたか？遅刻または欠席ですか？")
    await interaction.response.send_message("下記のメッセージにリアクションをつけてください。", ephemeral=True)

@tree.command(name="total", description="現在の出席状況を出力します。")
async def total_command(interaction: discord.Interaction):
    data = load_attendance_data()
    attendance_count, absence_count, attendance_ratio, remaining_days_for_pass, school_days, remaining_school_days, late_allowed_count = aggregate_attendance_data(data)

    embed = discord.Embed(title="出席状況の概要", color=discord.Color.blue())
    embed.add_field(name="年間授業日数", value=school_days, inline=False)
    embed.add_field(name="合計日数", value=attendance_count + absence_count, inline=False)
    embed.add_field(name="現在の出席回数", value=attendance_count, inline=False)
    embed.add_field(name="現在の欠席回数", value=absence_count, inline=False)
    embed.add_field(name="残りの授業日数", value=remaining_school_days, inline=False)
    embed.add_field(name="現在の出席割合", value=f"{attendance_ratio:.2f}%", inline=False)
    embed.add_field(name="登校しなければいけない回数", value=remaining_days_for_pass, inline=False)
    embed.add_field(name="遅刻できる回数", value=late_allowed_count, inline=False)
    
    await interaction.response.send_message(embed=embed)

@client.event
async def on_reaction_add(reaction, user):
    if user.bot or user.id != ALLOWED_USER_ID:
        return
    channel = client.get_channel(CHANNEL_ID)
    if reaction.message.channel.id != CHANNEL_ID:
        return
    if str(reaction.emoji) not in ['✅', '❌']:
        return
    data = load_attendance_data()
    today_status = "出席" if str(reaction.emoji) == '✅' else "遅刻"
    if today_status == "出席":
        data['attendance'] += 1
    else:
        data['absence'] += 1

    save_attendance_data(data)
    print(f'更新された出席状況 : {data}')
    
    attendance_count, absence_count, attendance_ratio, remaining_days_for_pass, school_days, remaining_school_days, late_allowed_count = aggregate_attendance_data(data)
    
    embed = discord.Embed(title=f"更新された出席状況 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})", color=discord.Color.green())
    embed.add_field(name="年間授業日数", value=school_days, inline=False)
    embed.add_field(name="合計日数", value=attendance_count + absence_count, inline=False)
    embed.add_field(name="現在の出席回数", value=attendance_count, inline=False)
    embed.add_field(name="現在の欠席回数", value=absence_count, inline=False)
    embed.add_field(name="残りの授業日数", value=remaining_school_days, inline=False)
    embed.add_field(name="現在の出席割合", value=f"{attendance_ratio:.2f}%", inline=False)
    embed.add_field(name="登校しなければいけない回数", value=remaining_days_for_pass, inline=False)
    embed.add_field(name="遅刻できる回数", value=late_allowed_count, inline=False)
    
    await reaction.message.delete()
    await channel.send(embed=embed)

async def send_to_discord(message):
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        msg = await channel.send(message)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
    else:
        print(f"Channel IDに一致するチャンネルがありません。\nChannel ID : {CHANNEL_ID}")

def run_schedule():
    while True:
        schedule.run_pending()
        sleep(1)

if __name__ == '__main__':
    schedule.every().day.at(schedule_time).do(lambda: asyncio.run_coroutine_threadsafe(check_and_notify(), client.loop))

    schedule_thread = threading.Thread(target=run_schedule)
    schedule_thread.start()
    
    client.run(TOKEN)
