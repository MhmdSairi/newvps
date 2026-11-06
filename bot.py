import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"

# Repository utama Anda yang sekarang sudah menjadi Publik
PUBLIC_REPO_NAME = "MhmdSairi/newvps"

# Penyimpanan token sementara per user ID
USER_TOKENS = {}

async def verify_railway_token(railway_token):
    """Fungsi login/validasi token asli ke Railway API v2."""
    url = "https://backboard.railway.com/graphql/v2"
    clean_token = railway_token.strip().replace('"', '').replace("'", "")
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }
    
    queries = [
        {"query": "{ me { id name email } }"},
        {"query": "{ workspaces { id name } }"},
        {"query": "{ projects { edges { node { id name } } } }"}
    ]
    
    for q in queries:
        try:
            response = requests.post(url, json=q, headers=headers, timeout=15)
            result = response.json()
            if "data" in result and result["data"]:
                return True, clean_token
        except Exception:
            continue
            
    return False, clean_token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan menu utama saat perintah /start dikirim."""
    keyboard = [
        [InlineKeyboardButton("🔑 Daftar Token (Login)", callback_data="menu_token")],
        [InlineKeyboardButton("🚀 Buat VPS (Auto Deploy)", callback_data="menu_deploy")],
        [InlineKeyboardButton("ℹ️ Cek Status Akun", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 **Bot Manager VPS & Railway Deployment**\n\n"
        "Selamat datang! Silakan daftarkan token Railway Anda. Setelah login, bot akan otomatis mendeploy instalasi VPS dari folder `vps2-main` di repository publik `MhmdSairi/newvps` ke akun Railway Anda."
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
                "Silakan pilih menu **Daftar Token (Login)** terlebih dahulu.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
                parse_mode="Markdown"
            )
            return
        
        await query.message.edit_text("🚀 **Bot sedang membuat project dan mendeploy folder `vps2-main` ke akun Railway Anda...**\nMohon tunggu beberapa saat.", parse_mode="Markdown")
        await execute_railway_api_deployment(query, user_id)
        
    elif query.data == "menu_status":
        user_id = query.from_user.id
        token_info = USER_TOKENS.get(user_id, {})
        if token_info:
            text = f"✅ **Akun Terhubung**\n• Nama Token: `{token_info.get('name')}`"
        else:
            text = "⚠️ Belum ada token Railway yang didaftarkan."
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "back_home":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap input format login token dari pengguna."""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_token'):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Format salah! Gunakan format:\n`NamaToken TokenRailway`\nContoh: `sairi rlwy_wksp_xxxx`", parse_mode="Markdown")
            return
        
        token_name, railway_token = parts[0], parts[1].strip()
        
        msg_wait = await update.message.reply_text("⏳ Memverifikasi token ke server Railway...")
        is_valid, clean_token = await verify_railway_token(railway_token)
        
        if not is_valid:
            await msg_wait.edit_text("❌ **Login Gagal!** Token Railway ditolak oleh server. Pastikan token Anda aktif dan benar.")
            return
        
        USER_TOKENS[user_id] = {
            "name": token_name,
            "token": clean_token
        }
        context.user_data['waiting_for_token'] = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Lanjut Buat VPS (Auto Deploy)", callback_data="menu_deploy")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]
        ]
        
        await msg_wait.edit_text(
            f"✅ **Login Berhasil & Token Disimpan!** 🎉\n\n"
            f"• Nama Token: `{token_name}`\n\n"
            f"Sekarang Anda bisa menekan tombol **Lanjut Buat VPS (Auto Deploy)** di bawah untuk mendeploy folder `vps2-main` dari repository `MhmdSairi/newvps`.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_railway_api_deployment(query, user_id):
    """Membuat project baru di akun Railway user dan mendeploy isi folder vps2-main dari repository publik."""
    token_data = USER_TOKENS.get(user_id)
    railway_token = token_data['token']
    
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    # 1. Buat Project Baru di Akun Railway User
    create_project_query = {
        "query": "mutation { projectCreate(input: { name: \"VPS-newvps-Deploy\" }) { id name } }"
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
        
        # 2. Buat Service yang menautkan repository publik Anda dengan rootDirectory "vps2-main"
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
                        "repo": PUBLIC_REPO_NAME,
                        "branch": "main",
                        "rootDirectory": "vps2-main"
                    }
                }
            }
        }
        
        service_res = requests.post(url, json=create_service_query, headers=headers, timeout=30)
        service_result = service_res.json()
        
        if "errors" in service_result:
            err_service = service_result["errors"][0].get("message", "Gagal menautkan repository")
            await query.message.reply_text(
                f"❌ **Proyek Dibuat, tapi Gagal Menautkan Repository:**\n`{err_service}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]),
                parse_mode="Markdown"
            )
            return
        
        await query.message.edit_text(
            f"✅ **Deployment Folder `vps2-main` Berhasil 100% Otomatis!** 🎉\n\n"
            f"• Project ID: `{project_id}`\n"
            f"• Sumber Repository: `{PUBLIC_REPO_NAME}`\n"
            f"• Direktori: `/vps2-main`\n\n"
            f"🚀 Bot telah sukses memerintahkan akun Railway pengguna untuk membuat project dan membangun VPS secara otomatis dari folder `vps2-main` repository Anda.",
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
    print("🤖 Memulai Bot Telegram Manager VPS (Public Repo Integration)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
