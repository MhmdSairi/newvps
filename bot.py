import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"

# Penyimpanan token dan detail akun per user ID
USER_TOKENS = {}

def fetch_railway_account_info(token: str):
    """Mengambil detail akun valid dari Railway menggunakan GraphQL API."""
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    query = """
    {
      me {
        id
        name
        email
      }
      projects {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if "errors" in result:
                return None, result["errors"][0].get("message", "Token ditolak")
            data = result.get("data", {})
            user_info = data.get("me", {})
            projects = [edge["node"]["name"] for edge in data.get("projects", {}).get("edges", [])]
            return {
                "name": user_info.get("name", "Railway User"),
                "email": user_info.get("email", "Tidak ada email"),
                "projects": projects
            }, None
        else:
            return None, f"HTTP Error Status: {response.status_code}"
    except Exception as e:
        return None, str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan menu utama saat perintah /start dikirim."""
    keyboard = [
        [InlineKeyboardButton("🔑 Daftar Token (Login)", callback_data="menu_token")],
        [InlineKeyboardButton("🚀 Buat VPS (Deploy)", callback_data="menu_deploy")],
        [InlineKeyboardButton("ℹ️ Cek Status Akun", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 **Bot Manager VPS & Railway Deployment**\n\n"
        "Selamat datang! Bot ini berfungsi untuk mendeploy template VPS Anda ke akun Railway secara otomatis.\n\n"
        "Silakan pilih menu di bawah ini:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani navigasi tombol inline menu."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_token":
        context.user_data['waiting_for_token'] = True
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(
            "🔑 **Silakan Kirim Token Railway Anda**\n\n"
            "Kirim format dengan spasi:\n`NamaToken TokenRailway`\n\n"
            "Contoh:\n`paier 35beedf9-xxxx`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif query.data == "menu_deploy":
        user_id = query.from_user.id
        if user_id not in USER_TOKENS:
            await query.message.edit_text(
                "❌ **Token Belum Terdaftar!**\n\n"
                "Silakan pilih menu **Daftar Token (Login)** terlebih dahulu untuk memasukkan token Railway Anda.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
                parse_mode="Markdown"
            )
            return
        
        await query.message.edit_text("🚀 **Menghubungkan ke API Railway & Membuat Proyek VPS...**\nMohon tunggu beberapa saat.", parse_mode="Markdown")
        await execute_railway_api_deployment(query, user_id)
        
    elif query.data == "menu_status":
        user_id = query.from_user.id
        token_info = USER_TOKENS.get(user_id, {})
        if token_info:
            acc_name = token_info.get('account_name', 'Terverifikasi')
            acc_email = token_info.get('account_email', '-')
            projects = token_info.get('projects', [])
            proj_str = ", ".join(projects[:3]) if projects else "Belum ada proyek"
            
            text = (
                f"✅ **AKUN TERHUBUNG & VALID**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Nama Sesi: `{token_info.get('name')}`\n"
                f"• Nama Railway: `{acc_name}`\n"
                f"• Email: `{acc_email}`\n"
                f"• Token Aktif: `{token_info.get('token')[:8]}...`\n"
                f"• Daftar Proyek: `{proj_str}`"
            )
        else:
            text = "⚠️ Belum ada token Railway yang didaftarkan."
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "back_home":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap input format token dari pengguna dan memvalidasinya secara nyata."""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_token'):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Format salah! Gunakan format:\n`NamaToken TokenRailway`\nContoh: `paier 35beedf9-xxxx`", parse_mode="Markdown")
            return
        
        token_name, railway_token = parts[0], parts[1]
        
        verifying_msg = await update.message.reply_text("⏳ **Memverifikasi Token ke API Railway...** Mohon tunggu sebentar.")
        
        # Validasi token dan ambil detail akun asli
        acc_data, err = fetch_railway_account_info(railway_token)
        if err or not acc_data:
            await verifying_msg.edit_text(f"❌ **Gagal Login / Token Tidak Valid:**\n`{err}`\n\nPastikan token Railway Anda benar.", parse_mode="Markdown")
            return
        
        # Simpan sesi user
        USER_TOKENS[user_id] = {
            "name": token_name,
            "token": railway_token,
            "account_name": acc_data["name"],
            "account_email": acc_data["email"],
            "projects": acc_data["projects"]
        }
        context.user_data['waiting_for_token'] = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Lanjut Buat VPS", callback_data="menu_deploy")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]
        ]
        
        await verifying_msg.edit_text(
            f"✅ **LOGIN BERHASIL & VALID!**\n\n"
            f"• Sesi: `{token_name}`\n"
            f"• Akun: `{acc_data['name']} ({acc_data['email']})`\n"
            f"• Token: `{railway_token[:8]}****`\n\n"
            f"Sekarang akun Anda terdeteksi aktif. Silakan tekan tombol **Lanjut Buat VPS** di bawah.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_railway_api_deployment(query, user_id):
    """Melakukan deploy menggunakan Railway GraphQL API secara langsung."""
    token_data = USER_TOKENS.get(user_id)
    railway_token = token_data['token']
    
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    # Query GraphQL untuk membuat Project baru
    create_project_query = {
        "query": "mutation { projectCreate(input: { name: \"My-VPS-Bot-Deploy\" }) { id name } }"
    }
    
    try:
        response = requests.post(url, json=create_project_query, headers=headers, timeout=30)
        result = response.json()
        
        if "errors" in result:
            err_msg = result["errors"][0].get("message", "Terjadi kesalahan API")
            await query.message.edit_text(
                f"❌ **Gagal membuat proyek Railway:**\n`{err_msg}`\n\nPastikan token Anda memiliki izin akses project.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
                parse_mode="Markdown"
            )
            return
            
        project_data = result.get("data", {}).get("projectCreate", {})
        project_id = project_data.get("id")
        project_name = project_data.get("name")
        
        await query.message.edit_text(
            f"🎉 **PROYEK VPS BERHASIL DIBUAT!**\n\n"
            f"• Nama Project: `{project_name}`\n"
            f"• Project ID: `{project_id}`\n\n"
            f"⏳ Proyek berhasil diinisialisasi di akun Railway Anda. Silakan buka dashboard Railway untuk melihat status build VPS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Terjadi kesalahan koneksi API:\n`{str(e)}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
            parse_mode="Markdown"
        )

def main():
    """Fungsi utama untuk menjalankan Bot Telegram."""
    print("🤖 Memulai Bot Telegram Manager VPS...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
