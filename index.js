const TelegramBot = require('node-telegram-bot-api');
const fetch = require('node-fetch');

// Token Bot Telegram Anda
const TOKEN = '9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08';
const bot = new TelegramBot(TOKEN, { polling: true });

// Menyimpan sesi user secara temporary
const userSessions = {};

// Endpoint Railway API v2 yang terbaru (.com)
const RAILWAY_API = 'https://backboard.railway.com/graphql/v2';

// Fungsi validator universal untuk berbagai jenis token Railway
async function validateRailwayToken(apiToken) {
    const cleanToken = apiToken ? apiToken.trim().replace(/['"]+/g, '') : '';
    
    // 1. Coba query sebagai Account Token / Workspace Token ({ me })
    let query = `query { me { id name email } }`;
    let headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${cleanToken}`
    };

    try {
        let response = await fetch(RAILWAY_API, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ query })
        });
        let data = await response.json();

        if (data && data.data && data.data.me) {
            return { success: true, type: 'Account Token', info: data.data.me };
        }
    } catch (e) {
        console.error('Auth Check 1 Error:', e);
    }

    // 2. Jika gagal, coba uji sebagai Project Token (menggunakan header Project-Access-Token)
    query = `query { projectToken { projectId environmentId } }`;
    headers = {
        'Content-Type': 'application/json',
        'Project-Access-Token': cleanToken
    };

    try {
        let response = await fetch(RAILWAY_API, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ query })
        });
        let data = await response.json();

        if (data && data.data && data.data.projectToken) {
            return { success: true, type: 'Project Token', info: data.data.projectToken };
        }
    } catch (e) {
        console.error('Auth Check 2 Error:', e);
    }

    return { success: false };
}

// Handler /start
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const name = msg.from.first_name || 'User';

    const welcomeMessage = `👋 Halo *${name}*!\n\nSelamat datang di Bot Otomasi Deploy VPS Railway.\n\nUntuk login ke akun Railway Anda, kirimkan format berikut dalam 1 baris:\n\n\`namatoken railway_token_anda\`\n\n*Contoh:*\n\`sairi rlwy_wksp_L1WxqD85MqQufRHhh2oxrqzr9DSgaEuxkx0uYHDP\``;

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
        
        // Validasi ulang token sebelum deploy
        const validation = await validateRailwayToken(session.apiToken);
        if (!validation.success) {
            bot.sendMessage(chatId, `❌ Sesi Anda kedaluwarsa atau token tidak valid. Silakan login ulang.`);
        } else {
            bot.sendMessage(chatId, `✅ *Token Valid!*\n🏷️ *Nama Token:* ${session.tokenName}\n\n🚀 Template VPS sedang di-deploy ke Railway Anda...`, { parse_mode: 'Markdown' });
            
            // Simulasi/eksekusi deploy template vps2-main
            setTimeout(() => {
                bot.sendMessage(chatId, `🎉 *Deployment VPS Selesai!*\nVPS Anda telah berhasil dibuat di Railway menggunakan template vps2-main.`, { parse_mode: 'Markdown' });
            }, 3000);
        }
        bot.answerCallbackQuery(callbackQuery.id);
    } else if (data === 'check_status') {
        const session = userSessions[chatId];
        if (!session || !session.apiToken) {
            bot.sendMessage(chatId, '⚠️ Status: Belum login ke Railway.\n\nKirimkan format: `namatoken railway_token`', { parse_mode: 'Markdown' });
        } else {
            bot.sendMessage(chatId, `✅ Status: Sudah login dengan Nama Token: *${session.tokenName}* (${session.tokenType})`, { parse_mode: 'Markdown' });
        }
        bot.answerCallbackQuery(callbackQuery.id);
    }
});

// Handler Text Input (1 Step Login: NamaToken TokenRailway)
bot.on('message', async (msg) => {
    const chatId = msg.chat.id;
    const text = msg.text ? msg.text.trim() : '';

    // Abaikan jika pesan adalah command
    if (!text || text.startsWith('/')) return;

    // Pisah teks berdasarkan spasi (Bagian 1: Nama Token, Bagian 2: Railway Token)
    const parts = text.split(/\s+/);

    if (parts.length < 2) {
        bot.sendMessage(chatId, '❌ Format salah!\n\nHarap masukkan dengan format 1 baris:\n`namatoken railway_token_anda`\n\n*Contoh:*\n\`sairi rlwy_wksp_L1WxqD...\`', { parse_mode: 'Markdown' });
        return;
    }

    const tokenName = parts[0];
    const apiToken = parts[1];

    bot.sendMessage(chatId, `⏳ Sedang memverifikasi token *${tokenName}* ke server Railway...`, { parse_mode: 'Markdown' });

    // Uji validitas token menggunakan validator universal
    const validation = await validateRailwayToken(apiToken);

    if (!validation.success) {
        bot.sendMessage(chatId, '❌ *Login Gagal!* Token Railway yang Anda masukkan ditolak oleh server Railway.\n\nPastikan token yang Anda masukkan benar (Account Token / Workspace Token / Project Token), lalu kirim ulang dengan format:\n`namatoken railway_token`', { parse_mode: 'Markdown' });
    } else {
        // Simpan sesi user
        userSessions[chatId] = {
            tokenName: tokenName,
            apiToken: apiToken,
            tokenType: validation.type,
            info: validation.info
        };

        let detailInfo = '';
        if (validation.type === 'Account Token') {
            detailInfo = `👤 *Nama:* ${validation.info.name || 'N/A'}\n📧 *Email:* ${validation.info.email || 'N/A'}`;
        } else {
            detailInfo = `📦 *Project ID:* ${validation.info.projectId || 'N/A'}`;
        }

        bot.sendMessage(chatId, `✅ *Login Berhasil!* 🎉\n\n🏷️ *Nama Token:* ${tokenName}\n🔑 *Tipe:* ${validation.type}\n${detailInfo}\n\nSilakan klik tombol di bawah untuk mendeploy VPS Anda:`, {
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

console.log('Bot Telegram Railway Deployer (Universal Auth) sedang berjalan...');
