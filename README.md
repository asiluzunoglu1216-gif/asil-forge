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

## Dosya Yapisi

- `app.py`: server, auth, routes, db logic
- `content.py`: metinler ve sabit icerikler
- `rendering.py`: HTML render katmani
- `static/styles.css`: arayuz sistemi
- `static/app.js`: mobil menu davranisi
- `data/asil_forge.db`: runtime database
- `.env.local`: git'e girmeyen gizli admin ve ortam ayarlari
