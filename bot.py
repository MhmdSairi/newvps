import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"

# Penyimpanan token dan detail akun per user ID
USER_TOKENS = {}

def fetch_railway_account_info(token: str):
    """Memverifikasi token secara nyata ke GraphQL API Railway."""
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
                "email": "Akses Aktif",
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
        [InlineKeyboardButton("🚀 Buat Proyek VPS", callback_data="menu_deploy")],
        [InlineKeyboardButton("ℹ️ Cek Status Akun", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 **Bot Manager VPS & Railway Deployment**\n\n"
        "Selamat datang! Bot ini terhubung langsung ke API Railway secara nyata (Real API).\n\n"
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
        
        status_msg = await query.message.edit_text("🚀 **Menghubungkan ke API Railway untuk Membuat Proyek Nyata...**", parse_mode="Markdown")
        await execute_real_railway_api_deployment(status_msg, user_id)
        
    elif query.data == "menu_status":
        user_id = query.from_user.id
        token_info = USER_TOKENS.get(user_id, {})
        if token_info:
            acc_name = token_info.get('account_name', 'Terverifikasi')
            projects = token_info.get('projects', [])
            proj_str = ", ".join(projects[:3]) if projects else "Belum ada proyek"
            
            text = (
                f"✅ **AKUN TERHUBUNG & VALID**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Nama Sesi: `{token_info.get('name')}`\n"
                f"• Jenis Token: `{acc_name}`\n"
                f"• Token Aktif: `{token_info.get('token')[:10]}...`\n"
                f"• Total Proyek di Akun: `{len(projects)}`"
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
        
        verifying_msg = await update.message.reply_text("⏳ **Memverifikasi Token secara nyata ke server Railway...**")
        
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
            "projects": acc_data["projects"]
        }
        context.user_data['waiting_for_token'] = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Buat Proyek VPS Nyata", callback_data="menu_deploy")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]
        ]
        
        await verifying_msg.edit_text(
            f"✅ **LOGIN 100% BERHASIL & TERVERIFIKASI!**\n\n"
            f"• Nama Sesi: `{token_name}`\n"
            f"• Tipe Token: `{acc_data['name']}`\n"
            f"• Token: `{railway_token[:10]}****`\n\n"
            f"Token terbukti valid di server Railway. Silakan tekan tombol di bawah untuk membuat proyek secara nyata.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_real_railway_api_deployment(status_msg, user_id):
    """Membuat proyek dan service langsung melalui GraphQL API Railway secara transparan dan nyata."""
    token_data = USER_TOKENS.get(user_id)
    railway_token = token_data['token']
    
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Authorization": f"Bearer {token_data['token']}",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. Buat Proyek Nyata
        create_project_query = {
            "query": "mutation { projectCreate(input: { name: \"VPS-Manager-Deploy\" }) { id name environments { edges { node { id } } } } }"
        }
        res = requests.post(url, json=create_project_query, headers=headers, timeout=30)
        res_json = res.json()
        
        if "errors" in res_json:
            err_msg = res_json["errors"][0].get("message", "Gagal membuat proyek")
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await status_msg.edit_text(f"❌ **Gagal membuat proyek di Railway:**\n`{err_msg}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        proj_data = res_json.get("data", {}).get("projectCreate", {})
        project_id = proj_data.get("id")
        project_name = proj_data.get("name")
        
        envs = proj_data.get("environments", {}).get("edges", [])
        env_id = envs[0]["node"]["id"] if envs else None

        # 2. Hubungkan Service dengan Repository publik Anda (newvps / vps2-main)
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
                    "name": "vps-installer-service",
                    "source": {
                        "repo": "MhmdSairi/newvps",
                        "branch": "main",
                        "rootDirectory": "vps2-main"
                    }
                }
            }
        }
        
        serv_res = requests.post(url, json=create_service_query, headers=headers, timeout=30)
        serv_json = serv_res.json()
        
        if "errors" in serv_json:
            err_msg = serv_json["errors"][0].get("message", "Gagal membuat service")
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await status_msg.edit_text(
                f"⚠️ **Proyek `{project_name}` Berhasil Dibuat, tapi gagal hubungkan repo:**\n`{err_msg}`\nCek dashboard Railway Anda, proyek sudah ada di sana.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return

        serv_data = serv_json.get("data", {}).get("serviceCreate", {})
        service_id = serv_data.get("id")

        # 3. Picu Deploy (Trigger Build)
        if env_id and service_id:
            deploy_query = {
                "query": """
                mutation ServiceInstanceDeployV2($serviceId: String!, $environmentId: String!) {
                  serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
                }
                """,
                "variables": {
                    "serviceId": service_id,
                    "environmentId": env_id
                }
            }
            requests.post(url, json=deploy_query, headers=headers, timeout=30)

        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
        await status_msg.edit_text(
            f"🎉 **PROYEK & DEPLOYMENT NYATA BERHASIL!**\n\n"
            f"• Nama Proyek: `{project_name}`\n"
            f"• Project ID: `{project_id}`\n"
            f"• Sumber Repo: `MhmdSairi/newvps` (Folder: `vps2-main`)\n\n"
            f"🚀 Silakan buka dashboard Railway Anda sekarang. Proyek **VPS-Manager-Deploy** benar-benar ada dan sedang memproses build file Anda secara nyata!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await status_msg.edit_text(f"❌ **Terjadi Kesalahan Koneksi API:**\n`{str(e)}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

def main():
    """Fungsi utama untuk menjalankan Bot Telegram."""
    print("🤖 Memulai Bot Telegram Manager VPS (Real API)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
