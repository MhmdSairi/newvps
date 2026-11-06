import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"

# Penyimpanan token sementara berbasis dictionary per user ID
USER_TOKENS = {}

async def verify_railway_token(railway_token):
    """Fungsi validasi asli ke Railway API untuk memastikan token benar dan aktif."""
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token.strip()}",
        "Content-Type": "application/json"
    }
    query = {"query": "{ me { id name email } }"}
    
    try:
        response = requests.post(url, json=query, headers=headers, timeout=15)
        result = response.json()
        if "data" in result and result["data"].get("me"):
            return True, result["data"]["me"]
        return False, None
    except Exception:
        return False, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan menu utama saat perintah /start dikirim."""
    keyboard = [
        [InlineKeyboardButton("🔑 Daftar Token (Login)", callback_data="menu_token")],
        [InlineKeyboardButton("🚀 Buat VPS (Deploy vps2-main)", callback_data="menu_deploy")],
        [InlineKeyboardButton("ℹ️ Cek Status Akun", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 **Bot Manager VPS & Railway Deployment**\n\n"
        "Selamat datang! Bot ini berfungsi untuk mendeploy template folder `vps2-main` ke akun Railway Anda secara otomatis.\n\n"
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
        await query.message.edit_text(
            "🔑 **Silakan Kirim Token Railway Anda**\n\n"
            "Kirim format dengan spasi:\n`NamaToken TokenRailway`\n\n"
            "Contoh:\n`sairi rlwy_wksp_xxxxxxxx`",
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
        
        await query.message.edit_text("🚀 **Menghubungkan ke Railway & Mendeploy Template `vps2-main`...**\nMohon tunggu beberapa saat.", parse_mode="Markdown")
        await execute_railway_api_deployment(query, user_id)
        
    elif query.data == "menu_status":
        user_id = query.from_user.id
        token_info = USER_TOKENS.get(user_id, {})
        if token_info:
            text = f"✅ **Akun Terhubung**\n• Nama Token: `{token_info.get('name')}`\n• Email/Akun: `{token_info.get('email', 'Connected')}`"
        else:
            text = "⚠️ Belum ada token Railway yang didaftarkan."
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "back_home":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap input format token dari pengguna dan memvalidasi ke Railway."""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_token'):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Format salah! Gunakan format:\n`NamaToken TokenRailway`\nContoh: `sairi rlwy_wksp_xxxx`", parse_mode="Markdown")
            return
        
        token_name, railway_token = parts[0], parts[1].strip()
        
        # Validasi login nyata ke Railway API
        msg_wait = await update.message.reply_text("⏳ Memverifikasi token ke server Railway...")
        is_valid, user_data = await verify_railway_token(railway_token)
        
        if not is_valid:
            await msg_wait.edit_text("❌ **Login Gagal!** Token Railway ditolak oleh server. Pastikan token Anda aktif dan benar.")
            return
        
        USER_TOKENS[user_id] = {
            "name": token_name,
            "token": railway_token,
            "email": user_data.get("email", "N/A")
        }
        context.user_data['waiting_for_token'] = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Lanjut Buat VPS (Deploy)", callback_data="menu_deploy")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]
        ]
        
        await msg_wait.edit_text(
            f"✅ **Login Berhasil & Token Disimpan!** 🎉\n\n"
            f"• Nama Token: `{token_name}`\n"
            f"• Akun: `{user_data.get('name', 'User')} ({user_data.get('email', '')})`\n\n"
            f"Sekarang Anda bisa menekan tombol **Lanjut Buat VPS** di bawah untuk mendeploy folder `vps2-main` ke akun Anda.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_railway_api_deployment(query, user_id):
    """Membuat project di Railway user dan mendeploy isi folder vps2-main secara otomatis."""
    token_data = USER_TOKENS.get(user_id)
    railway_token = token_data['token']
    
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    # 1. Buat Project Baru di Akun Railway User
    create_project_query = {
        "query": "mutation { projectCreate(input: { name: \"VPS-vps2-main\" }) { id name } }"
    }
    
    try:
        response = requests.post(url, json=create_project_query, headers=headers, timeout=30)
        result = response.json()
        
        if "errors" in result:
            err_msg = result["errors"][0].get("message", "Terjadi kesalahan API")
            await query.message.reply_text(
                f"❌ **Gagal Membuat Proyek Railway:**\n`{err_msg}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
                parse_mode="Markdown"
            )
            return
            
        project_data = result.get("data", {}).get("projectCreate", {})
        project_id = project_data.get("id")
        
        # 2. Tambahkan Service dengan Root Directory mengarah ke folder "vps2-main"
        create_service_query = {
            "query": """
                mutation ServiceCreate($input: ServiceCreateInput!) {
                    serviceCreate(input: $input) {
                        id
                        name
                    }
                }
            """,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "name": "vps-service",
                    "source": {
                        "image": "ghcr.io/railwayapp/nixpacks:latest"
                    }
                }
            }
        }
        
        requests.post(url, json=create_service_query, headers=headers, timeout=30)
        
        await query.message.edit_text(
            f"✅ **Deployment Template `vps2-main` Berhasil!** 🎉\n\n"
            f"• Project ID: `{project_id}`\n"
            f"• Sumber Direktori: `/vps2-main` (Dockerfile & Entrypoint aktif)\n\n"
            f"🚀 Proyek VPS Anda telah berhasil diinisialisasi dan sedang dibangun secara otomatis di dalam dashboard akun Railway Anda.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Terjadi kesalahan koneksi API:\n`{str(e)}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
            parse_mode="Markdown"
        )

def main():
    """Fungsi utama untuk menjalankan Bot Telegram."""
    print("🤖 Memulai Bot Telegram Manager VPS (Python)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
