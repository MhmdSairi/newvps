
const TelegramBot = require('node-telegram-bot-api');
const fetch = require('node-fetch');

// Ganti dengan Token Bot Telegram Anda dari @BotFather atau ambil dari Environment Variable
const TOKEN = process.env.BOT_TOKEN || '9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08';
const bot = new TelegramBot(TOKEN, { polling: true });

// Menyimpan sesi user secara temporary (untuk production, gunakan database seperti SQLite/MongoDB)
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
                'Authorization': `Bearer ${apiToken}`
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

    const welcomeMessage = `👋 Halo *${name}*!\n\nSelamat datang di Bot Otomasi Deploy VPS Railway.\nBot ini berfungsi sebagai perantara untuk menghubungkan akun Railway Anda dan mendeploy template VPS secara instan.\n\nSilakan pilih menu di bawah ini:`;

    const opts = {
        parse_mode: 'Markdown',
        reply_markup: {
            inline_keyboard: [
                [{ text: '🔑 Login Akun Railway', callback_data: 'login_railway' }],
                [{ text: 'ℹ️ Cek Status Akun', callback_data: 'check_status' }]
            ]
        }
    };

    bot.sendMessage(chatId, welcomeMessage, opts);
});

// Handler Callback Queries
bot.on('callback_query', async (callbackQuery) => {
    const msg = callbackQuery.message;
    const chatId = msg.chat.id;
    const data = callbackQuery.data;

    if (data === 'login_railway') {
        userSessions[chatId] = { step: 'waiting_token_name' };
        bot.sendMessage(chatId, '📝 *Langkah 1/2*\n\nSilakan masukkan *Nama Token* Railway Anda (Contoh: `MyTokenDeploy`):', { parse_mode: 'Markdown' });
        bot.answerCallbackQuery(callbackQuery.id);
    } else if (data === 'deploy_vps') {
        const session = userSessions[chatId];
        if (!session || !session.apiToken) {
            bot.sendMessage(chatId, '❌ Anda belum login ke akun Railway. Silakan klik /start lalu pilih *Login Akun Railway* terlebih dahulu.');
            bot.answerCallbackQuery(callbackQuery.id);
            return;
        }

        bot.sendMessage(chatId, '⏳ Sedang memproses deployment template VPS ke akun Railway Anda...');
        
        // Contoh query GraphQL Railway untuk cek user / membuat project
        const userQuery = `{ me { id name email } }`;
        const result = await railwayQuery(session.apiToken, userQuery);

        if (result.errors || result.error) {
            bot.sendMessage(chatId, `❌ Gagal terhubung ke Railway. Token Anda mungkin tidak valid.\nError: ${JSON.stringify(result.errors || result.error)}`);
        } else {
            const userInfo = result.data.me;
            bot.sendMessage(chatId, `✅ *Berhasil Terhubung!*\n\nAkun: ${userInfo.name} (${userInfo.email})\n\n🚀 Template VPS sedang di-deploy ke Railway Anda...`, { parse_mode: 'Markdown' });
            
            // Di sini Anda bisa menambahkan logika provisioning/deploy template GitHub repo Anda ke Railway menggunakan Railway API mutations.
            // Contoh simulasi sukses deploy:
            setTimeout(() => {
                bot.sendMessage(chatId, `🎉 *Deployment VPS Selesai!*\n\nVPS Anda telah berhasil dibuat di Railway menggunakan template vps2-main. Silakan cek dashboard Railway Anda.`, { parse_mode: 'Markdown' });
            }, 3000);
        }
        bot.answerCallbackQuery(callbackQuery.id);
    } else if (data === 'check_status') {
        const session = userSessions[chatId];
        if (!session || !session.apiToken) {
            bot.sendMessage(chatId, '⚠️ Status: Belum login ke Railway.');
        } else {
            bot.sendMessage(chatId, `✅ Status: Sudah login dengan Token Name: *${session.tokenName || 'N/A'}*`, { parse_mode: 'Markdown' });
        }
        bot.answerCallbackQuery(callbackQuery.id);
    }
});

// Handler Text Input untuk Proses Login Interaktif
bot.on('message', async (msg) => {
    const chatId = msg.chat.id;
    const text = msg.text;

    // Abaikan jika pesan adalah command (/start, dll)
    if (!text || text.startsWith('/')) return;

    const session = userSessions[chatId];
    if (!session) return;

    if (session.step === 'waiting_token_name') {
        session.tokenName = text.trim();
        session.step = 'waiting_token_secret';
        bot.sendMessage(chatId, `📝 *Langkah 2/2*\n\nNama Token diterima: *${session.tokenName}*\n\nSekarang, silakan masukkan *Railway API Token* Anda (Account Token / Project Token):`, { parse_mode: 'Markdown' });
    } else if (session.step === 'waiting_token_secret') {
        session.apiToken = text.trim();
        session.step = 'logged_in';

        // Validasi token dengan test query ke Railway API
        const testRes = await railwayQuery(session.apiToken, '{ me { id name } }');

        if (testRes.errors || testRes.error) {
            delete userSessions[chatId];
            bot.sendMessage(chatId, '❌ *Login Gagal!* Token Railway yang Anda masukkan tidak valid.\nSilakan ketik /start untuk mengulang.');
        } else {
            const userName = testRes.data.me.name || 'User';
            bot.sendMessage(chatId, `✅ *Login Berhasil!*\n\nSelamat datang, *${userName}*! Akun Railway Anda berhasil dihubungkan ke bot.\n\nKlik tombol di bawah untuk mulai mendepositkan/mendeploy VPS template Anda:`, {
                parse_mode: 'Markdown',
                reply_markup: {
                    inline_keyboard: [
                        [{ text: '🚀 Buat Akun VPS (Deploy)', callback_data: 'deploy_vps' }],
                        [{ text: '🔄 Ganti Akun / Logout', callback_data: 'login_railway' }]
                    ]
                }
            });
        }
    }
});

console.log('Bot Telegram Railway Deployer sedang berjalan...');
