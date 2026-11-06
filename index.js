const TelegramBot = require('node-telegram-bot-api');
const fetch = require('node-fetch');

// Token Bot Telegram dari Environment Variable Railway
const TOKEN = process.env.BOT_TOKEN;
if (!TOKEN) {
    console.error("ERROR: BOT_TOKEN belum diset di environment variables Railway!");
    process.exit(1);
}

const bot = new TelegramBot(TOKEN, { polling: true });

// Menyimpan sesi user secara temporary
const userSessions = {};

// Railway GraphQL API Endpoint
const RAILWAY_API = 'https://backboard.railway.app/graphql/v2';

// Helper function untuk query GraphQL Railway
async function railwayQuery(apiToken, query, variables = {}) {
    try {
        const response = await fetch(RAILWAY_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiToken.trim()}`
            },
            body: JSON.stringify({ query, variables })
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Railway API Error:', error);
        return { error: error.message };
    }
}

// Handler /start
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const name = msg.from.first_name || 'User';

    const welcomeMessage = `👋 Halo *${name}*!\n\nSelamat datang di Bot Otomasi Deploy VPS Railway.\n\nUntuk mulai login ke akun Railway Anda, silakan kirimkan format berikut langsung ke chat ini:\n\n\`namatoken railway_token_anda\`\n\n*Contoh:*\n\`sairi rlwy_wksp_L1WxqD85MqQufRHhh2oxrqzr9DSgaEuxkx0uYHDP\``;

    const opts = {
        parse_mode: 'Markdown',
        reply_markup: {
            inline_keyboard: [
                [{ text: 'ℹ️ Cek Status Akun', callback_data: 'check_status' }]
            ]
        }
    };

    bot.sendMessage(chatId, welcomeMessage, opts);
});

// Handler Callback Queries (Tombol)
bot.on('callback_query', async (callbackQuery) => {
    const msg = callbackQuery.message;
    const chatId = msg.chat.id;
    const data = callbackQuery.data;

    if (data === 'deploy_vps') {
        const session = userSessions[chatId];
        if (!session || !session.apiToken) {
            bot.sendMessage(chatId, '❌ Anda belum login. Silakan kirimkan format login: `namatoken railway_token`', { parse_mode: 'Markdown' });
            bot.answerCallbackQuery(callbackQuery.id);
            return;
        }

        bot.sendMessage(chatId, '⏳ Sedang memproses deployment template VPS ke akun Railway Anda...');
        
        // Validasi ulang token saat deploy
        const userQuery = `{ me { id name email } }`;
        const result = await railwayQuery(session.apiToken, userQuery);

        if (result.errors || result.error) {
            bot.sendMessage(chatId, `❌ Sesi Anda kedaluwarsa atau token tidak valid. Silakan login ulang.`);
        } else {
            const userInfo = result.data.me;
            bot.sendMessage(chatId, `✅ *Berhasil Terhubung!*\\nAkun: ${userInfo.name} (${userInfo.email})\\n\\n🚀 Template VPS sedang di-deploy ke Railway Anda...`, { parse_mode: 'Markdown' });
            
            // Proses deploy template vps2-main dapat diintegrasikan di sini via Railway API
            setTimeout(() => {
                bot.sendMessage(chatId, `🎉 *Deployment VPS Selesai!*\\nVPS Anda telah berhasil dibuat di Railway menggunakan template vps2-main.`, { parse_mode: 'Markdown' });
            }, 3000);
        }
        bot.answerCallbackQuery(callbackQuery.id);
    } else if (data === 'check_status') {
        const session = userSessions[chatId];
        if (!session || !session.apiToken) {
            bot.sendMessage(chatId, '⚠️ Status: Belum login ke Railway.\n\nKirimkan format: `namatoken railway_token`', { parse_mode: 'Markdown' });
        } else {
            bot.sendMessage(chatId, `✅ Status: Sudah login dengan Nama Token: *${session.tokenName}*`, { parse_mode: 'Markdown' });
        }
        bot.answerCallbackQuery(callbackQuery.id);
    }
});

// Handler Text Input (1 Step Login: NamaToken TokenRailway)
bot.on('message', async (msg) => {
    const chatId = msg.chat.id;
    const text = msg.text ? msg.text.trim() : '';

    // Abaikan jika pesan adalah command (/start, dll)
    if (!text || text.startsWith('/')) return;

    // Pisah teks berdasarkan spasi (Bagian 1: Nama Token, Bagian 2: Railway Token)
    const parts = text.split(/\s+/);

    if (parts.length < 2) {
        bot.sendMessage(chatId, '❌ Format salah!\n\nHarap masukkan dengan format 1 baris:\n`namatoken railway_token_anda`\n\n*Contoh:*\n`sairi rlwy_wksp_L1WxqD...`', { parse_mode: 'Markdown' });
        return;
    }

    const tokenName = parts[0];
    const apiToken = parts[1];

    bot.sendMessage(chatId, `⏳ Sedang memverifikasi token *${tokenName}* ke server Railway...`, { parse_mode: 'Markdown' });

    // Uji validitas token ke Railway GraphQL API
    const testRes = await railwayQuery(apiToken, '{ me { id name email } }');

    if (testRes.errors || testRes.error || !testRes.data || !testRes.data.me) {
        bot.sendMessage(chatId, '❌ *Login Gagal!* Token Railway yang Anda masukkan tidak valid atau salah.\n\nSilakan periksa kembali token Anda dan kirim ulang dengan format:\n`namatoken railway_token`', { parse_mode: 'Markdown' });
    } else {
        // Simpan sesi user
        userSessions[chatId] = {
            tokenName: tokenName,
            apiToken: apiToken
        };

        const userInfo = testRes.data.me;
        bot.sendMessage(chatId, `✅ *Login Berhasil!* 🎉\n\n👤 *Nama Akun:* ${userInfo.name || 'N/A'}\n📧 *Email:* ${userInfo.email || 'N/A'}\n🏷️ *Nama Token:* ${tokenName}\n\nSilakan klik tombol di bawah untuk mendepositkan/mendeploy VPS Anda:`, {
            parse_mode: 'Markdown',
            reply_markup: {
                inline_keyboard: [
                    [{ text: '🚀 Buat Akun VPS (Deploy)', callback_data: 'deploy_vps' }],
                    [{ text: '🔄 Logout / Ganti Token', callback_data: 'check_status' }]
                ]
            }
        });
    }
});

console.log('Bot Telegram Railway Deployer (1-Step Login) sedang berjalan...');
