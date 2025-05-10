import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import datetime
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Настройка интента для бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Создание бота
bot = commands.Bot(command_prefix='!', intents=intents)

# Подключение к базе данных
conn = sqlite3.connect('hrbot.db')
cursor = conn.cursor()

# Создание таблиц базы данных если они не существуют
def setup_database():
    # Таблица для черного списка
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY,
        discord_tag TEXT,
        passport_number TEXT,
        list_type TEXT,
        reason TEXT,
        expiry_date TEXT NULL,
        added_at TEXT,
        added_by TEXT
    )
    ''')
    
    # Таблица для аудитов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY,
        discord_tag TEXT,
        id_number TEXT,
        employee_name TEXT,
        employee_passport TEXT,
        action_type TEXT,
        action_reason TEXT,
        audit_date TEXT,
        server_id TEXT
    )
    ''')
    
    conn.commit()

# Проверка, находится ли пользователь в черном списке
def is_blacklisted(discord_tag=None, passport=None):
    if discord_tag:
        cursor.execute("SELECT * FROM blacklist WHERE discord_tag = ?", (discord_tag,))
        result = cursor.fetchone()
        if result:
            return result
    
    if passport:
        cursor.execute("SELECT * FROM blacklist WHERE passport_number = ?", (passport,))
        result = cursor.fetchone()
        if result:
            return result
    
    return None

# Добавление пользователя в черный список
def add_to_blacklist(discord_tag, passport, list_type, reason, expiry_date, added_by):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO blacklist (discord_tag, passport_number, list_type, reason, expiry_date, added_at, added_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (discord_tag, passport, list_type, reason, expiry_date, current_time, added_by)
    )
    conn.commit()

# Удаление пользователя из черного списка
def remove_from_blacklist(discord_tag=None, passport=None):
    if discord_tag:
        cursor.execute("DELETE FROM blacklist WHERE discord_tag = ?", (discord_tag,))
    
    if passport:
        cursor.execute("DELETE FROM blacklist WHERE passport_number = ?", (passport,))
    
    conn.commit()

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен и готов к работе!')
    setup_database()
    try:
        synced = await bot.tree.sync()
        print(f'Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'Ошибка синхронизации команд: {e}')

# Команда /audit
@bot.tree.command(name="audit", description="Создать запись кадрового аудита")
@app_commands.describe(
    id_number="Номер служебного удостоверения",
    employee_name="ФИО сотрудника",
    employee_passport="Номер паспорта сотрудника",
    action_type="Тип кадрового действия",
    action_reason="Основание кадрового действия"
)
async def audit(interaction: discord.Interaction, id_number: str, employee_name: str, employee_passport: str, action_type: str, action_reason: str):
    # Проверка канала и роли
    if interaction.channel.id != 1369770031109640314:
        await interaction.response.send_message("Эта команда может использоваться только в специальном канале!", ephemeral=True)
        return
    
    # Проверка роли пользователя
    if not any(role.id == 1130178461898641512 for role in interaction.user.roles):
        await interaction.response.send_message("У вас нет прав для использования этой команды!", ephemeral=True)
        return
    
    discord_tag = str(interaction.user)
    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Проверка черного списка
    blacklist_entry = is_blacklisted(passport=employee_passport)
    
    # Сохранение данных аудита
    cursor.execute(
        "INSERT INTO audits (discord_tag, id_number, employee_name, employee_passport, action_type, action_reason, audit_date, server_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (discord_tag, id_number, employee_name, employee_passport, action_type, action_reason, current_date, str(interaction.guild.id))
    )
    conn.commit()
    
    # Создание embed-сообщения
    embed = discord.Embed(
        title="Кадровый аудит",
        color=discord.Color.blue()
    )
    embed.add_field(name="Сотрудник", value=discord_tag, inline=True)
    embed.add_field(name="Номер удостоверения", value=id_number, inline=True)
    embed.add_field(name="ФИО", value=employee_name, inline=False)
    embed.add_field(name="Паспорт", value=employee_passport, inline=True)
    embed.add_field(name="Тип действия", value=action_type, inline=True)
    embed.add_field(name="Основание", value=action_reason, inline=False)
    embed.set_footer(text=f"Дата: {current_date}")
    
    await interaction.response.send_message(embed=embed)
    
    # Если найдено совпадение в черном списке, отправить уведомление
    if blacklist_entry:
        notification_channel = bot.get_channel(1370791808308740186)
        if notification_channel:
            warning_embed = discord.Embed(
                title="⚠️ ПРЕДУПРЕЖДЕНИЕ: Совпадение с черным списком!",
                description=f"Обнаружено совпадение в черном списке при аудите!",
                color=discord.Color.red()
            )
            warning_embed.add_field(name="Сервер", value=interaction.guild.name, inline=False)
            warning_embed.add_field(name="Запросил", value=discord_tag, inline=True)
            warning_embed.add_field(name="Кто в ЧС", value=f"Паспорт: {employee_passport}", inline=True)
            warning_embed.add_field(name="Причина внесения в ЧС", value=blacklist_entry[4], inline=False)
            
            # Создание кнопок для действий
            class BlacklistActions(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=None)
                
                @discord.ui.button(label="✅ Разрешить", style=discord.ButtonStyle.green)
                async def approve_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    await button_interaction.response.send_message(f"Действие разрешено несмотря на ЧС", ephemeral=True)
                    self.disable_all_items()
                    await button_interaction.message.edit(view=self)
                
                @discord.ui.button(label="❌ Удалить из ЧС", style=discord.ButtonStyle.red)
                async def remove_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    remove_from_blacklist(passport=employee_passport)
                    await button_interaction.response.send_message(f"Пользователь удален из черного списка", ephemeral=True)
                    self.disable_all_items()
                    await button_interaction.message.edit(view=self)
            
            await notification_channel.send(embed=warning_embed, view=BlacklistActions())

# Команда /blacklist
@bot.tree.command(name="blacklist", description="Добавить пользователя в черный список")
@app_commands.describe(
    discord_tag="Discord-тег пользователя (например, user#1234)",
    passport="Номер паспорта",
    list_type="Тип черного списка",
    reason="Причина добавления в ЧС",
    expiry_date="Срок (опционально, формат: ДД.ММ.ГГГГ)"
)
@app_commands.choices(list_type=[
    app_commands.Choice(name="Фракция", value="faction"),
    app_commands.Choice(name="Общий", value="general")
])
async def blacklist(interaction: discord.Interaction, discord_tag: str, passport: str, list_type: app_commands.Choice[str], reason: str, expiry_date: str = None):
    # Проверка роли пользователя
    if not any(role.id == 1130177420620746865 for role in interaction.user.roles):
        await interaction.response.send_message("У вас нет прав для использования этой команды!", ephemeral=True)
        return
    
    # Добавление в черный список
    add_to_blacklist(discord_tag, passport, list_type.value, reason, expiry_date, str(interaction.user))
    
    # Создание подтверждающего embed-сообщения
    embed = discord.Embed(
        title="Добавление в черный список",
        description=f"Пользователь успешно добавлен в черный список",
        color=discord.Color.red()
    )
    embed.add_field(name="Discord", value=discord_tag, inline=True)
    embed.add_field(name="Паспорт", value=passport, inline=True)
    embed.add_field(name="Тип списка", value=list_type.name, inline=True)
    embed.add_field(name="Причина", value=reason, inline=False)
    if expiry_date:
        embed.add_field(name="Срок действия", value=expiry_date, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Запуск бота
bot.run(TOKEN)
