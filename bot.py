import os
import json
import time
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Token Bot Telegram Anda
TELEGRAM_BOT_TOKEN = "9286169112:AAHLD7pusm7iLhC2dtHvSm5x0B8L0G2IG08"
DB_FILE = "railway_users.json"

def load_db():
    """Memuat database sesi user agar tidak terhapus."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    """Menyimpan database sesi user secara permanen."""
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Gagal menyimpan DB: {e}")

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
            projects = [{"id": edge["node"]["id"], "name": edge["node"]["name"]} for edge in data.get("projects", {}).get("edges", [])]
            token_type = "Workspace Token" if "rlwy_wksp_" in token else "Account / Personal Token"
            
            return {
                "name": token_type,
                "projects": projects
            }, None
        else:
            return None, f"HTTP Error Status: {response.status_code}"
    except Exception as e:
        return None, str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan menu utama."""
    user_id = str(update.effective_user.id)
    db = load_db()
    user_info = db.get(user_id)

    keyboard = [
        [InlineKeyboardButton("🔑 Daftar / Ganti Token", callback_data="menu_token")],
        [InlineKeyboardButton("🚀 Buat & Deploy VPS", callback_data="menu_deploy")],
        [InlineKeyboardButton("📂 Cek Proyek Railway", callback_data="menu_list_projects")],
        [InlineKeyboardButton("ℹ️ Status Sesi", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_text = f"✅ Sesi Aktif: `{user_info['token_name']}`" if user_info else "⚠️ Belum login token Railway."
    
    welcome_text = (
        "🤖 **Bot Manager VPS & Railway Deployment**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_text}\n\n"
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
    user_id = str(query.from_user.id)
    db = load_db()
    
    if query.data == "menu_token":
        context.user_data['waiting_for_token'] = True
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(
            "🔑 **Silakan Kirim Token Railway Anda**\n\n"
            "Kirim dengan format:\n`NamaToken TokenRailway`\n\n"
            "Contoh:\n`myvps rlwy_wksp_xxxx`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    elif query.data == "menu_deploy":
        if user_id not in db:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await query.message.edit_text(
                "❌ **Token Belum Terdaftar!**\nSilakan daftarkan token Anda terlebih dahulu melalui menu **Daftar / Ganti Token**.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        status_msg = await query.message.edit_text(
            "🚀 **Memulai Inisialisasi Proyek VPS...**",
            parse_mode="Markdown"
        )
        await execute_real_railway_deployment(status_msg, user_id)
        
    elif query.data == "menu_list_projects":
        if user_id not in db:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await query.message.edit_text("❌ Token belum terdaftar.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        await query.message.edit_text("⏳ Mengambil daftar proyek dari akun Railway Anda...", parse_mode="Markdown")
        await show_projects_list(query.message, user_id)
        
    elif query.data.startswith("delete_proj_"):
        proj_id = query.data.replace("delete_proj_", "")
        await delete_railway_project(query, user_id, proj_id)
        
    elif query.data == "menu_status":
        user_info = db.get(user_id, {})
        if user_info:
            text = (
                f"✅ **INFORMASI SESI (PERMANEN)**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Nama Sesi: `{user_info.get('token_name')}`\n"
                f"• Tipe Token: `{user_info.get('account_type')}`\n"
                f"• Token Aktif: `{user_info.get('token')[:12]}...`"
            )
        else:
            text = "⚠️ Belum ada sesi token tersimpan."
            
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "back_home":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap input token dan menyimpannya secara permanen."""
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_token'):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await update.message.reply_text(
                "❌ Format salah! Gunakan format:\n`NamaToken TokenRailway`\nContoh: `myvps rlwy_wksp_xxxx`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        token_name, railway_token = parts[0], parts[1]
        
        verifying_msg = await update.message.reply_text("⏳ **Memverifikasi Token ke Server Railway...**")
        
        acc_data, err = fetch_railway_account_info(railway_token)
        if err or not acc_data:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await verifying_msg.edit_text(
                f"❌ **Gagal Login / Token Tidak Valid:**\n`{err}`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        # Simpan ke Database JSON (Permanen / Tidak Terhapus)
        db = load_db()
        db[user_id] = {
            "token_name": token_name,
            "token": railway_token,
            "account_type": acc_data["name"]
        }
        save_db(db)
        
        context.user_data['waiting_for_token'] = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Lanjut Buat VPS", callback_data="menu_deploy")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]
        ]
        
        await verifying_msg.edit_text(
            f"✅ **LOGIN BERHASIL & SESI DISIMPAN PERMANEN!**\n\n"
            f"• Nama Sesi: `{token_name}`\n"
            f"• Tipe Token: `{acc_data['name']}`\n\n"
            f"Sesi Anda aman dan tersimpan. Silakan tekan tombol **Lanjut Buat VPS** di bawah.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def execute_real_railway_deployment(status_msg, user_id):
    """Membuat proyek, mengatur rootDirectory, memicu deploy, menampilkan animasi loading, dan mengambil log SSH."""
    db = load_db()
    token_data = db.get(user_id)
    headers = {
        "Authorization": f"Bearer {token_data['token']}",
        "Content-Type": "application/json"
    }
    url = "https://backboard.railway.com/graphql/v2"
    
    try:
        # 1. Buat Proyek Baru
        create_project_query = {
            "query": "mutation { projectCreate(input: { name: \"VPS-Manager-Deploy\" }) { id name environments { edges { node { id } } } } }"
        }
        res = requests.post(url, json=create_project_query, headers=headers, timeout=30).json()
        
        if "errors" in res:
            await status_msg.edit_text(f"❌ Gagal buat proyek: `{res['errors'][0]['message']}`", parse_mode="Markdown")
            return
            
        proj_data = res.get("data", {}).get("projectCreate", {})
        project_id = proj_data.get("id")
        project_name = proj_data.get("name")
        env_id = proj_data.get("environments", {}).get("edges", [])[0]["node"]["id"]

        # 2. Buat Service dari Repo newvps
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
                    "name": "vps-installer",
                    "source": {
                        "repo": "MhmdSairi/newvps"
                    }
                }
            }
        }
        serv_res = requests.post(url, json=create_service_query, headers=headers, timeout=30).json()
        if "errors" in serv_res:
            await status_msg.edit_text(f"❌ Gagal membuat service: `{serv_res['errors'][0]['message']}`", parse_mode="Markdown")
            return

        service_id = serv_res.get("data", {}).get("serviceCreate", {}).get("id")

        # 3. Atur Root Directory ke "vps2-main" dan Picu Deploy
        update_instance_query = {
            "query": """
            mutation ServiceInstanceUpdate($serviceId: String!, $environmentId: String!,$input: ServiceInstanceUpdateInput!) {
              serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input:$input)
            }
            """,
            "variables": {
                "serviceId": service_id,
                "environmentId": env_id,
                "input": {"rootDirectory": "vps2-main"}
            }
        }
        requests.post(url, json=update_instance_query, headers=headers, timeout=30)

        deploy_query = {
            "query": """
            mutation ServiceInstanceDeployV2($serviceId: String!,$environmentId: String!) {
              serviceInstanceDeployV2(serviceId: $serviceId, environmentId:$environmentId)
            }
            """,
            "variables": {"serviceId": service_id, "environmentId": env_id}
        }
        requests.post(url, json=deploy_query, headers=headers, timeout=30)

        # 4. Animasi Loading & Menunggu Deploy Selesai (Hingga 5 Menit / 30 Iterasi x 10 Detik)
        loaders = [
            "📦 `[■□□□□□□□□□]` 10%",
            "📦 `[■■□□□□□□□□]` 20%",
            "📦 `[■■■□□□□□□□]` 30%",
            "📦 `[■■■■□□□□□□]` 40%",
            "📦 `[■■■■■□□□□□]` 50%",
            "📦 `[■■■■■■□□□□]` 60%",
            "📦 `[■■■■■■■□□□]` 70%",
            "📦 `[■■■■■■■■□□]` 80%",
            "📦 `[■■■■■■■■■□]` 90%",
            "📦 `[■■■■■■■■■■]` 100%"
        ]

        ssh_details = None
        log_query = {
            "query": """
            query DeploymentLogs($environmentId: String!,$serviceId: String!) {
              deploymentLogs(environmentId: $environmentId, serviceId:$serviceId) {
                message
              }
            }
            """,
            "variables": {"environmentId": env_id, "serviceId": service_id}
        }

        for i in range(30):  # Total waktu maksimal 5 menit (30 x 10 detik)
            loader_anim = loaders[i % len(loaders)]
            elapsed_time = (i + 1) * 10
            
            try:
                await status_msg.edit_text(
                    f"🚀 **Penginstalan Railway Ubuntu 24.04 VPS sedang berjalan mohon ditunggu 2-3 menit**\n\n"
                    f"{loader_anim}\n"
                    f"⏱️ Waktu berlalu: `{elapsed_time} detik` (Maks. 5 menit)\n"
                    f"📂 Proyek: `{project_name}`\n\n"
                    f"_Bot sedang membaca log secara real-time hingga detail SSH muncul..._",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

            await asyncio.sleep(10)

            # Ambil log terbaru dari Railway
            log_res = requests.post(url, json=log_query, headers=headers, timeout=30).json()
            logs = log_res.get("data", {}).get("deploymentLogs", [])
            full_log_text = "\n".join([item.get("message", "") for item in logs])
            
            # Cek apakah string penanda SSH Access Details sudah muncul
            if "SSH ACCESS DETAILS" in full_log_text or "Password" in full_log_text:
                ssh_details = full_log_text
                break

        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
        
        if ssh_details:
            # Ambil bagian penting dari SSH Access Details sampai ke password
            lines = ssh_details.split("\n")
            filtered_lines = []
            capture = False
            for line in lines:
                if "SSH ACCESS DETAILS" in line:
                    capture = True
                if capture:
                    filtered_lines.append(line)
                    if "Password" in line or "SSH Command" in line:
                        pass
            
            clean_log = "\n".join(filtered_lines[:15]) # Ambil batas baris yang rapi
            
            await status_msg.edit_text(
                f"🎉 **PENGINSTALAN VPS SELESAI & ONLINE!**[span_1](start_span)[span_1](end_span)\n\n"
                f"📂 **Proyek:** `{project_name}`\n\n"
                f"🔑 **DATA AKSES SSH ANDA:**\n"
                f"```text\n{clean_log}\n```",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                f"⚠️ **Waktu Tunggu Maksimal Tercapai (5 Menit)**\n\n"
                f"Proyek `{project_name}` telah dibuat dan dideploy, namun log SSH belum sempat tertangkap otomatis oleh bot. Silakan cek detail akses langsung melalui Dashboard Railway Anda.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await status_msg.edit_text(f"❌ **Terjadi Kesalahan:**\n`{str(e)}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_projects_list(message, user_id):
    """Menampilkan daftar proyek aktif di akun Railway beserta tombol hapus."""
    db = load_db()
    token_data = db.get(user_id)
    headers = {
        "Authorization": f"Bearer {token_data['token']}",
        "Content-Type": "application/json"
    }
    url = "https://backboard.railway.com/graphql/v2"
    query = """
    {
      projects {
        edges {
          node {
            id
            name
            createdAt
          }
        }
      }
    }
    """
    try:
        res = requests.post(url, json={"query": query}, headers=headers, timeout=15).json()
        edges = res.get("data", {}).get("projects", {}).get("edges", [])
        
        if not edges:
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            await message.edit_text("📂 Belum ada proyek yang ditemukan di akun Railway Anda.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        keyboard = []
        text = "📂 **DAFTAR PROYEK RAILWAY ANDA:**\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        for edge in edges:
            node = edge["node"]
            proj_name = node["name"]
            proj_id = node["id"]
            text += f"• **{proj_name}** (`{proj_id[:8]}...`)\n"
            keyboard.append([InlineKeyboardButton(f"🗑 Hapus Proyek: {proj_name}", callback_data=f"delete_proj_{proj_id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_home")])
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
        await message.edit_text(f"❌ Gagal mengambil daftar proyek: `{str(e)}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def delete_railway_project(query, user_id, proj_id):
    """Menghapus proyek dari Railway berdasarkan Project ID."""
    db = load_db()
    token_data = db.get(user_id)
    headers = {
        "Authorization": f"Bearer {token_data['token']}",
        "Content-Type": "application/json"
    }
    url = "https://backboard.railway.com/graphql/v2"
    mutation = {
        "query": """
        mutation ProjectDelete($id: String!) {
          projectDelete(id: $id)
        }
        """,
        "variables": {"id": proj_id}
    }
    
    try:
        res = requests.post(url, json=mutation, headers=headers, timeout=30).json()
        if "errors" in res:
            err = res["errors"][0].get("message", "Gagal menghapus")
            await query.message.edit_text(f"❌ Gagal menghapus proyek: `{err}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="menu_list_projects")]]))
            return
            
        keyboard = [[InlineKeyboardButton("📂 Lihat Daftar Proyek", callback_data="menu_list_projects")], [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
        await query.message.edit_text("🗑 **PROYEK BERHASIL DIHAPUS DARI RAILWAY!**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    except Exception as e:
        await query.message.edit_text(f"❌ Terjadi kesalahan saat menghapus: `{str(e)}`")

def main():
    """Fungsi utama untuk menjalankan Bot Telegram."""
    print("🤖 Memulai Bot Telegram Manager VPS (Final Version)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
