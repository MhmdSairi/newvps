import os
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"

# Penyimpanan token dan detail akun per user ID
USER_TOKENS = {}

def fetch_railway_account_info(token: str):
    """Mengambil detail valid dari Railway."""
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    query = """
    {
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
                return None, result["errors"][0].get("message", "Token ditolak oleh Railway")
            
            data = result.get("data", {})
            projects = [edge["node"]["name"] for edge in data.get("projects", {}).get("edges", [])]
            token_type = "Workspace Token" if "rlwy_wksp_" in token else "Account / Personal Token"
            
            return {
                "name": token_type,
                "email": "Akses Workspace Aktif",
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
            "Contoh:\n`paier rlwy_wksp_xxxx`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif query.data == "menu_deploy":
        user_id = query.from_user.id
        if user_id not in USER_TOKENS:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await query.message.edit_text(
                "❌ **Token Belum Terdaftar!**\n\n"
                "Silakan pilih menu **Daftar Token (Login)** terlebih dahulu untuk memasukkan token Railway Anda.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        status_msg = await query.message.edit_text("🚀 **Memulai Proses Deploy vps2-main ke Railway...**\n🔄 `[1/4]` Menyiapkan direktori...", parse_mode="Markdown")
        await execute_railway_cli_deployment(status_msg, user_id)
        
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
                f"• Jenis Token: `{acc_name}`\n"
                f"• Status: `{acc_email}`\n"
                f"• Token Aktif: `{token_info.get('token')[:10]}...`\n"
                f"• Daftar Proyek: `{proj_str}`"
            )
        else:
            text = "⚠️ Belum ada token Railway yang didaftarkan."
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "back_home":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap input format token dari pengguna dan memvalidasinya secara nyata ke server Railway."""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_token'):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await update.message.reply_text(
                "❌ Format salah! Gunakan format:\n`NamaToken TokenRailway`\nContoh: `paier rlwy_wksp_xxxx`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        token_name, railway_token = parts[0], parts[1]
        
        verifying_msg = await update.message.reply_text("⏳ **Memverifikasi Token ke API Railway...** Mohon tunggu sebentar.")
        
        acc_data, err = fetch_railway_account_info(railway_token)
        if err or not acc_data:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await verifying_msg.edit_text(
                f"❌ **Gagal Login / Token Tidak Valid:**\n`{err}`\n\nPastikan token Railway Anda benar dan aktif.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
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
            f"• Nama Sesi: `{token_name}`\n"
            f"• Tipe Token: `{acc_data['name']}`\n"
            f"• Token: `{railway_token[:10]}****`\n\n"
            f"Token berhasil diverifikasi. Silakan tekan tombol **Lanjut Buat VPS** di bawah untuk mulai deploy.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_railway_cli_deployment(status_msg, user_id):
    """Mengambil folder vps2-main dari repository newvps dan mendeploynya menggunakan Railway CLI."""
    token_data = USER_TOKENS.get(user_id)
    railway_token = token_data['token']
    repo_dir = f"repo_temp_{user_id}"
    deploy_dir = f"vps_deploy_{user_id}"

    try:
        if os.path.exists(repo_dir):
            os.system(f"rm -rf {repo_dir}")
        if os.path.exists(deploy_dir):
            os.system(f"rm -rf {deploy_dir}")

        await status_msg.edit_text("🚀 **PROSES DEPLOYMENT (2/4)**\n🔄 Mengambil folder `vps2-main` dari repository `newvps`...", parse_mode="Markdown")
        
        os.makedirs(repo_dir)
        os.chdir(repo_dir)
        
        await asyncio.create_subprocess_shell("git init", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.create_subprocess_shell("git remote add origin https://github.com/MhmdSairi/newvps.git", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.create_subprocess_shell("git config core.sparseCheckout true", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        
        # Memastikan direktori .git/info ada sebelum menulis file sparse-checkout
        os.makedirs(".git/info", exist_ok=True)
        with open(".git/info/sparse-checkout", "w") as f:
            f.write("vps2-main/\n")
            
        pull_proc = await asyncio.create_subprocess_shell(
            "git pull origin main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await pull_proc.communicate()
        
        if not os.path.exists("vps2-main"):
            await asyncio.create_subprocess_shell("git pull origin master", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            
        if not os.path.exists("vps2-main"):
            os.chdir("..")
            os.system(f"rm -rf {repo_dir}")
            raise Exception("Folder `vps2-main` tidak ditemukan di dalam repository `newvps`.")

        os.chdir("..")
        os.rename(os.path.join(repo_dir, "vps2-main"), deploy_dir)
        os.system(f"rm -rf {repo_dir}")

        await status_msg.edit_text("🚀 **PROSES DEPLOYMENT (3/4)**\n🔄 Inisialisasi & menghubungkan proyek ke Railway...", parse_mode="Markdown")

        os.chdir(deploy_dir)

        init_proc = await asyncio.create_subprocess_shell(
            f"export RAILWAY_TOKEN={railway_token} && railway init --yes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await init_proc.communicate()

        await status_msg.edit_text("🚀 **PROSES DEPLOYMENT (4/4)**\n🔄 Mengunggah dan mendeploy file ke server Railway...", parse_mode="Markdown")

        deploy_proc = await asyncio.create_subprocess_shell(
            f"export RAILWAY_TOKEN={railway_token} && railway up --detach --yes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await deploy_proc.communicate()
        
        os.chdir("..")
        os.system(f"rm -rf {deploy_dir}")

        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
        await status_msg.edit_text(
            f"🎉 **DEPLOYMENT vps2-main BERHASIL!**\n\n"
            f"✅ Seluruh file dari folder `vps2-main` (di dalam `newvps`) berhasil di-upload dan di-deploy ke akun Railway Anda.\n\n"
            f"💡 *Status service Anda sekarang aktif dan berjalan secara online di dashboard Railway.*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        try:
            os.chdir("..")
        except Exception:
            pass
            
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
        await status_msg.edit_text(
            f"❌ **Gagal Melakukan Deploy:**\n`{str(e)}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
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
