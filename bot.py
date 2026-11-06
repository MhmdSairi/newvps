import asyncio
import logging
import json
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Konfigurasi Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"
ADMIN_TELEGRAM_ID = 1564275538
DB_FILE = "railway_users.json"

USER_SESSIONS = {}

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Gagal membaca database: {e}")
    
    env_backup = os.environ.get("BOT_PERSISTENT_DB")
    if env_backup:
        try:
            data = json.loads(env_backup)
            save_db(data)
            return data
        except Exception as e:
            logger.error(f"Gagal memuat DB dari ENV: {e}")
            
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
        os.environ["BOT_PERSISTENT_DB"] = json.dumps(data)
    except Exception as e:
        logger.error(f"Gagal menyimpan database: {e}")

def verify_railway_token(token: str):
    """Memverifikasi token railway ke API GraphQL Railway dan mengambil detail akun."""
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
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if "errors" in result:
                return None, f"Token ditolak oleh Railway: {result['errors'][0]['message']}"
            data = result.get("data", {})
            user_info = data.get("me", {})
            projects = [edge["node"]["name"] for edge in data.get("projects", {}).get("edges", [])]
            return {
                "name": user_info.get("name", "Railway User"),
                "email": user_info.get("email", "No Email"),
                "projects": projects
            }, None
        else:
            return None, f"Gagal terhubung ke Railway (HTTP Status: {response.status_code})"
    except Exception as e:
        return None, f"Kesalahan koneksi verifikasi: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("⛔ **Akses Ditolak:** Bot ini bersifat privat.")
        return

    chat_id = str(update.effective_chat.id)
    db = load_db()
    user_data = db.get(chat_id, {})

    if user_data and user_data.get("railway_token"):
        await show_main_menu(update.message, user_data)
    else:
        keyboard = [
            [InlineKeyboardButton("🔑 LOGIN TOKEN RAILWAY", callback_data="login_railway")],
            [InlineKeyboardButton("ℹ️ CARA DAPAT TOKEN", callback_data="help_token")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "✨ **BOT AUTOMATION DEPLOY VPS RAILWAY** ✨\n\n"
            "Belum ada Token Railway yang tersimpan. Silakan login terlebih dahulu menggunakan Token Railway Anda:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def show_main_menu(target_obj, user_data):
    token_name = user_data.get("token_name", "Default User")
    railway_name = user_data.get("railway_name", "-")
    railway_email = user_data.get("railway_email", "-")
    masked_token = user_data.get("railway_token", "")[:10] + "..."
    projects = user_data.get("projects", [])
    project_list = ", ".join(projects[:3]) if projects else "Belum ada / Default"
    
    text = (
        "✨ **PANEL UTAMA DEPLOYMENT VPS** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Nama Sesi**   : `{token_name}`\n"
        f"👤 **Akun Railway** : `{railway_name} ({railway_email})`\n"
        f"🔑 **Token Aktif** : `{masked_token}`\n"
        f"📁 **Proyek Aktif** : `{project_list}`\n"
        f"📦 **Repository**  : `vps2-main` (Public GitHub)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Pilih menu di bawah untuk mengelola atau menjalankan deploy otomatis.*"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 DEPLOY SEKARANG", callback_data="start_deploy")],
        [InlineKeyboardButton("🔄 GANTI TOKEN LOGIN", callback_data="login_railway")],
        [InlineKeyboardButton("❌ KELUAR / RESET", callback_data="logout_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(target_obj, 'edit_message_text'):
        await target_obj.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif hasattr(target_obj, 'reply_text'):
        await target_obj.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        chat_id = target_obj.effective_chat.id if hasattr(target_obj, 'effective_chat') else target_obj.chat.id
        await target_obj.get_bot().send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    db = load_db()

    if query.data == "login_railway":
        USER_SESSIONS[chat_id] = {'status': 'AWAITING_TOKEN_NAME'}
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU UTAMA", callback_data="back_to_home")]]
        await query.message.edit_text(
            "🔑 **LOGIN TOKEN RAILWAY**\n\n"
            "Langkah 1/2: Silakan ketik **Nama Sesi / Nama Anda**:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "help_token":
        keyboard = [
            [InlineKeyboardButton("🔑 LOGIN SEKARANG", callback_data="login_railway")],
            [InlineKeyboardButton("🏠 KEMBALI KE MENU UTAMA", callback_data="back_to_home")]
        ]
        await query.message.edit_text(
            "ℹ️ **CARA MENDAPATKAN TOKEN RAILWAY:**\n\n"
            "1. Buka dashboard Railway (railway.com).\n"
            "2. Masuk ke **Account Settings** atau **Workspace Tokens**.\n"
            "3. Buat token baru (berformat `rlwy_wksp_...`).\n"
            "4. Salin token tersebut dan masukkan ke bot saat diminta.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "start_deploy":
        user_data = db.get(chat_id, {})
        railway_token = user_data.get("railway_token")
        
        if not railway_token:
            await query.message.edit_text("❌ Token tidak ditemukan. Silakan login ulang.")
            return

        status_msg = await query.message.reply_text(
            "⏳ **MEMPROSES DEPLOYMENT OTO-VPS**\n\n"
            "🔄 `[1/4]` Mengunduh file `vps2-main` dari GitHub...",
            parse_mode="Markdown"
        )

        try:
            folder_name = f"deploy_{chat_id}"
            if os.path.exists(folder_name):
                os.system(f"rm -rf {folder_name}")

            # 1. Clone repository publik GitHub
            process = await asyncio.create_subprocess_shell(
                f"git clone https://github.com/MhmdSairi/vps2-main.git {folder_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            await status_msg.edit_text(
                "⏳ **MEMPROSES DEPLOYMENT OTO-VPS**\n\n"
                "✅ `[1/4]` Berhasil mengunduh file repository.\n"
                "🔄 `[2/4]` Melakukan autentikasi Railway CLI...",
                parse_mode="Markdown"
            )

            os.chdir(folder_name)
            
            # 2. Login CLI menggunakan token
            login_proc = await asyncio.create_subprocess_shell(
                f"export RAILWAY_TOKEN={railway_token} && railway login --browserless",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await login_proc.communicate()

            await status_msg.edit_text(
                "⏳ **MEMPROSES DEPLOYMENT OTO-VPS**\n\n"
                "✅ `[1/4]` File repository diunduh.\n"
                "✅ `[2/4]` Autentikasi Railway sukses.\n"
                "🔄 `[3/4]` Inisialisasi & menghubungkan proyek Railway...",
                parse_mode="Markdown"
            )

            # 3. Inisialisasi atau link proyek railway
            init_proc = await asyncio.create_subprocess_shell(
                f"export RAILWAY_TOKEN={railway_token} && railway init --yes",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await init_proc.communicate()

            await status_msg.edit_text(
                "⏳ **MEMPROSES DEPLOYMENT OTO-VPS**\n\n"
                "✅ `[1/4]` File repository diunduh.\n"
                "✅ `[2/4]` Autentikasi Railway sukses.\n"
                "✅ `[3/4]` Proyek diinisialisasi.\n"
                "🔄 `[4/4]` Mengunggah dan menjalankan perintah `railway up`...",
                parse_mode="Markdown"
            )

            # 4. Deploy ke Railway secara detached
            deploy_process = await asyncio.create_subprocess_shell(
                f"export RAILWAY_TOKEN={railway_token} && railway up --detach --yes",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await deploy_process.communicate()
            os.chdir("..")

            keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU UTAMA", callback_data="back_to_home")]]
            await status_msg.edit_text(
                "🎉 **DEPLOYMENT BERHASIL DIEKSEKUSI!**\n\n"
                "✅ `[1/4]` File repository diunduh.\n"
                "✅ `[2/4]` Autentikasi token sukses.\n"
                "✅ `[3/4]` Inisialisasi proyek selesai.\n"
                "✅ `[4/4]` Perintah `railway up` berhasil dikirim!\n\n"
                "💡 *VPS installer Anda sedang berjalan di cloud Railway.*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        except Exception as e:
            if os.getcwd().endswith(folder_name):
                os.chdir("..")
            keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU UTAMA", callback_data="back_to_home")]]
            await status_msg.edit_text(f"❌ **Gagal melakukan deploy:**\n`{str(e)}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "logout_session":
        if chat_id in db:
            del db[chat_id]
            save_db(db)
        
        keyboard = [[InlineKeyboardButton("🔑 LOGIN KEMBALI", callback_data="login_railway")]]
        await query.message.edit_text(
            "🔒 **SESI BERHASIL DIHAPUS**\n\nToken dan data login Anda telah dihapus dari database bot.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "back_to_home":
        user_data = db.get(chat_id, {})
        if user_data and user_data.get("railway_token"):
            await show_main_menu(query.message, user_data)
        else:
            keyboard = [
                [InlineKeyboardButton("🔑 LOGIN TOKEN RAILWAY", callback_data="login_railway")],
                [InlineKeyboardButton("ℹ️ CARA DAPAT TOKEN", callback_data="help_token")]
            ]
            await query.message.edit_text(
                "✨ **BOT AUTOMATION DEPLOY VPS RAILWAY** ✨\n\nSilakan login terlebih dahulu:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_TELEGRAM_ID:
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()
    session = USER_SESSIONS.get(chat_id, {})
    status = session.get('status')

    if status == 'AWAITING_TOKEN_NAME':
        USER_SESSIONS[chat_id]['token_name'] = text
        USER_SESSIONS[chat_id]['status'] = 'AWAITING_RAILWAY_TOKEN'
        
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU UTAMA", callback_data="back_to_home")]]
        await update.message.reply_text(
            f"✅ Nama Sesi dicatat: `{text}`\n\n"
            "Langkah 2/2: Sekarang silakan ketik / kirim **Token Railway** Anda (contoh: `rlwy_wksp_...`):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif status == 'AWAITING_RAILWAY_TOKEN':
        token_name = session.get('token_name', 'My Token')
        railway_token = text

        verifying_msg = await update.message.reply_text("⏳ **Memverifikasi Token Railway ke server...** Mohon tunggu sebentar.")

        # Lakukan verifikasi nyata ke API Railway
        account_data, err_msg = verify_railway_token(railway_token)

        if err_msg or not account_data:
            keyboard = [[InlineKeyboardButton("🔑 COBA LOGIN LAGI", callback_data="login_railway")]]
            await verifying_msg.edit_text(
                f"❌ **LOGIN GAGAL!**\n\n`{err_msg}`\n\nPastikan token Railway yang Anda masukkan sudah benar.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            if chat_id in USER_SESSIONS:
                del USER_SESSIONS[chat_id]
            return

        db = load_db()
        db[chat_id] = {
            "token_name": token_name,
            "railway_token": railway_token,
            "railway_name": account_data["name"],
            "railway_email": account_data["email"],
            "projects": account_data["projects"]
        }
        save_db(db)

        if chat_id in USER_SESSIONS:
            del USER_SESSIONS[chat_id]

        await verifying_msg.edit_text("🎉 **VERIFIKASI & LOGIN BERHASIL!** Detail akun Anda berhasil dimuat.")
        await show_main_menu(update, db[chat_id])

def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🤖 Memulai Bot Deploy VPS Railway...")
    application.run_polling()

if __name__ == '__main__':
    main()
