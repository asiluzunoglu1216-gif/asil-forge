# Asil Forge

Python stdlib ile kurulan tam sayfa bir yazilim sirketi platformu:

- public company website
- login / register / forgot password
- email verification token flow
- user dashboard
- project request system
- admin panel
- notification outbox
- SQLite persistence

## Calistirma

Once yerel ortam degiskeni dosyasi olustur:

```powershell
copy .env.example .env.local
```

Sonra `.env.local` icindeki admin bilgilerini kendine gore degistir.

Ornek:

```env
ASIL_FORGE_ADMIN_EMAIL=admin@asilforge.local
ASIL_FORGE_ADMIN_PASSWORD=BurayaGucluBirSifreYaz
```

Ardindan:

```powershell
python app.py
```

Sonra tarayicida su adresi ac:

`http://127.0.0.1:8000`

## Render Yayini

Render uzerinde yayinlamak icin bu repo dogrudan kullanilabilir.

Onerilen ayarlar:

- Service Type: `Web Service`
- Runtime: `Python`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python app.py`

Render ortami icin uygulama artik otomatik olarak `0.0.0.0:$PORT` uzerinden acilir.

Render ortam degiskenleri:

- `ASIL_FORGE_ADMIN_EMAIL`
- `ASIL_FORGE_ADMIN_PASSWORD`
- `AF_SECRET_KEY`
- `AF_BASE_URL`

## Vercel Yayini

Vercel icin repo artik `api/index.py` ve `vercel.json` ile function tabanli calisacak sekilde hazirlandi.

Vercel proje ayarlari:

- Framework Preset: `Other` veya `Python`
- Root Directory: `./`
- Install Command: `pip install -r requirements.txt`
- Build Command: bos birak
- Output Directory: bos birak

Vercel Environment Variables:

- `ASIL_FORGE_ADMIN_EMAIL`
- `ASIL_FORGE_ADMIN_PASSWORD`
- `AF_SECRET_KEY`
- `AF_BASE_URL`

Ornek `AF_BASE_URL`:

```env
AF_BASE_URL=https://asil-forge.vercel.app
```

Not: Vercel ortami kalici yerel SQLite depolamasi icin uygun degildir. Bu repo Vercel'de demo / hafif kullanim icin gecici `/tmp` veritabani ile acilir. Gercek uretim kullaniminda harici bir veritabani kullanilmalidir.

## Dosya Yapisi

- `app.py`: server, auth, routes, db logic
- `content.py`: metinler ve sabit icerikler
- `rendering.py`: HTML render katmani
- `static/styles.css`: arayuz sistemi
- `static/app.js`: mobil menu davranisi
- `data/asil_forge.db`: runtime database
- `.env.local`: git'e girmeyen gizli admin ve ortam ayarlari
