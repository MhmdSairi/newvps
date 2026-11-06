# Railway VPS Deploy Bot

Bot Telegram perantara untuk login akun Railway menggunakan Token Name & Token API, serta melakukan deploy template VPS secara otomatis.

## Fitur
1. **Login Interaktif**: User memasukkan Nama Token dan Railway API Token langsung via chat Telegram.
2. **Validasi Otomatis**: Bot memverifikasi token ke Railway GraphQL API.
3. **Deploy VPS Otomatis**: Tombol khusus `Buat Akun VPS` untuk mendeploy template ke akun user.

## Cara Deploy ke Railway / GitHub
1. Upload file ini ke repository GitHub Anda.
2. Buat Project baru di Railway dan hubungkan repository ini.
3. Set Environment Variable di Railway:
   - `BOT_TOKEN`: Token bot Telegram Anda dari @BotFather.
4. Bot siap digunakan!
