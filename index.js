// Discord Audit Bot для системы учета кадровых манипуляций
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, EmbedBuilder, PermissionsBitField } = require('discord.js');
const http = require('http');
require('dotenv').config();

// Проверка наличия токена
if (!process.env.DISCORD_TOKEN) {
  console.error('ОШИБКА: Токен Discord бота не найден в переменных окружения.');
  console.error('Убедитесь, что файл .env создан и содержит DISCORD_TOKEN=ваш_токен_бота');
  process.exit(1);
}

// Проверка наличия CLIENT_ID
if (!process.env.CLIENT_ID) {
  console.error('ОШИБКА: CLIENT_ID не найден в переменных окружения.');
  console.error('Убедитесь, что файл .env содержит CLIENT_ID=id_вашего_приложения');
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers // Добавлен интент для работы с участниками сервера
  ]
});

// ID канала, где будет работать бот
const AUDIT_CHANNEL_ID = '1369770031109640314';
// ID роли, которая может использовать команду
const AUTHORIZED_ROLE_ID = '1130178461898641512';

// Создаем slash-команду на русском языке
const auditCommand = new SlashCommandBuilder()
  .setName('audit')
  .setDescription('Создать аудиторскую запись о кадровой манипуляции')
  .addStringOption(option =>
    option.setName('офицер')
      .setDescription('Ваше ФИО и номер служебного удостоверения')
      .setRequired(true))
  .addUserOption(option =>
    option.setName('сотрудник')
      .setDescription('Выберите сотрудника, в отношении которого производится манипуляция')
      .setRequired(true))
  .addStringOption(option =>
    option.setName('паспорт')
      .setDescription('Номер паспорта гражданина (сотрудника)')
      .setRequired(true))
  .addStringOption(option =>
    option.setName('основание')
      .setDescription('Основание для осуществления кадровой манипуляции')
      .setRequired(true))
  .addStringOption(option => 
    option.setName('дата')
      .setDescription('Дата осуществления кадровой манипуляции (ДД.ММ.ГГГГ)')
      .setRequired(true));

// Регистрация slash-команд
const registerCommands = async () => {
  try {
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
    const commands = [auditCommand.toJSON()];
    
    console.log('Регистрация slash-команд...');
    
    await rest.put(
      Routes.applicationCommands(process.env.CLIENT_ID),
      { body: commands }
    );
    
    console.log('Slash-команды успешно зарегистрированы');
  } catch (error) {
    console.error('Ошибка при регистрации команд:', error);
  }
};

client.once('ready', () => {
  console.log(`Бот ${client.user.tag} успешно запущен!`);
  registerCommands();
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isCommand()) return;
  if (interaction.commandName !== 'audit') return;
  
  // Проверка канала
  if (interaction.channelId !== AUDIT_CHANNEL_ID) {
    return interaction.reply({ 
      content: 'Эта команда может использоваться только в специальном канале аудита.', 
      ephemeral: true 
    });
  }
  
  // Проверка роли
  if (!interaction.member.roles.cache.has(AUTHORIZED_ROLE_ID)) {
    return interaction.reply({ 
      content: 'У вас нет прав для использования этой команды.', 
      ephemeral: true 
    });
  }
  
  // Получаем данные из формы
  const officerInfo = interaction.options.getString('офицер');
  const targetUser = interaction.options.getUser('сотрудник');
  const passport = interaction.options.getString('паспорт');
  const reason = interaction.options.getString('основание');
  const date = interaction.options.getString('дата');
  
  // Получаем информацию о целевом пользователе
  const targetMember = await interaction.guild.members.fetch(targetUser.id);
  
  // Извлекаем должность и имя из никнейма (формат: "ДОЛЖНОСТЬ | Имя и Фамилия")
  let position = "Не указана";
  let employeeName = targetUser.username;
  
  if (targetMember.nickname) {
    const nicknameParts = targetMember.nickname.split('|');
    if (nicknameParts.length >= 2) {
      position = nicknameParts[0].trim();
      employeeName = nicknameParts[1].trim();
    }
  }
  
  // Создаем красивое embed-сообщение
  const auditEmbed = new EmbedBuilder()
    .setColor(0x2B2D31)
    .setTitle('📋 Запись о кадровой манипуляции')
    .setDescription(`**Информация о сотруднике:** ${targetUser}`)
    .setTimestamp()
    .addFields(
      { name: '👤 Аудитор', value: officerInfo, inline: false },
      { name: '📝 ФИО сотрудника', value: employeeName, inline: false },
      { name: '🪪 Номер паспорта', value: passport, inline: false },
      { name: '🔰 Должность', value: position, inline: false },
      { name: '📄 Основание', value: reason, inline: false },
      { name: '📅 Дата манипуляции', value: date, inline: false }
    )
    .setFooter({ text: 'Система аудита кадровых манипуляций' });
  
  await interaction.reply({ embeds: [auditEmbed] });
});

// Обработка ошибок
client.on('error', error => {
  console.error('Ошибка Discord клиента:', error);
  
  if (error.message.includes('TokenInvalid')) {
    console.error('---------------------------------------------------');
    console.error('ОШИБКА: Предоставлен недопустимый токен Discord бота.');
    console.error('Возможные причины:');
    console.error('1. Токен введен неверно или содержит ошибки');
    console.error('2. Токен устарел или был сброшен');
    console.error('3. Бот был удален из Discord Developer Portal');
    console.error('---------------------------------------------------');
    console.error('Решение:');
    console.error('1. Проверьте токен в файле .env');
    console.error('2. Создайте новый токен в Discord Developer Portal');
    console.error('3. Перезапустите бота с правильным токеном');
    console.error('---------------------------------------------------');
    process.exit(1);
  }
});

process.on('unhandledRejection', error => {
  console.error('Необработанная ошибка:', error);
  
  if (error.message.includes('TokenInvalid')) {
    console.error('---------------------------------------------------');
    console.error('ОШИБКА: Предоставлен недопустимый токен Discord бота.');
    console.error('Перезапустите бота с правильным токеном в файле .env');
    console.error('---------------------------------------------------');
    process.exit(1);
  }
});

// Создаем простой HTTP сервер для health checks на Render.com
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200);
    res.end('Bot is running!');
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(process.env.PORT || 3000, () => {
  console.log(`HTTP сервер запущен на порту ${process.env.PORT || 3000}`);
});

// Запуск бота с обработкой ошибок
try {
  console.log('Попытка входа в систему...');
  client.login(process.env.DISCORD_TOKEN)
    .catch(error => {
      console.error('Ошибка при входе:', error.message);
      if (error.message.includes('TokenInvalid')) {
        console.error('Недопустимый токен. Проверьте файл .env и убедитесь, что токен верный.');
      } else if (error.message.includes('disallowed intents')) {
        console.error('Ошибка интентов. Проверьте, что в Discord Developer Portal включены все необходимые интенты.');
      }
      process.exit(1);
    });
} catch (error) {
  console.error('Критическая ошибка при запуске бота:', error);
  process.exit(1);
}
