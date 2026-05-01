# Sub Link Manager 📡

V2Ray/Xray master subscription link တစ်ခုကို user အလိုက် expiry date နဲ့ ခွဲဝေပေးတဲ့ Python web app။

## Features
- 🔐 Admin login
- 📋 Master sub link အများကြီး ထည့်နိုင်
- 👥 User တစ်ယောက်ချင်းစီအတွက် unique sub link generate
- ⏰ Expiry date သတ်မှတ် (7d / 1mo / 2mo / 3mo / 6mo / 1yr)
- 🔄 Extend (သက်တမ်းတိုး) လုပ်နိုင်
- 📊 Last used tracking
- 🚫 Expire ဖြစ်ရင် auto block

## အလုပ်လုပ်ပုံ
1. Admin က master sub link (သင့် `q7softsux.art/api/subscription?user=...` ကဲ့သို့) ထည့်
2. User တစ်ယောက်အတွက် sub link generate → `https://yourdomain.com/sub/abc123xyz`
3. User က V2Ray/v2rayN/Hiddify/Streisand client ထဲ ထည့်
4. App က expiry check → ok ဖြစ်ရင် master content forward → expire ရင် empty

## Local Run
```bash
pip install -r requirements.txt
ADMIN_PASSWORD=mysecret python main.py
# http://localhost:8000
```

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `ADMIN_USERNAME` | `admin` | Admin login username |
| `ADMIN_PASSWORD` | `changeme` | **⚠️ မဖြစ်မနေပြောင်းပါ** |
| `SECRET_KEY` | random | Session encryption key |
| `PUBLIC_BASE_URL` | auto | e.g. `https://sub.yourdomain.com` |
| `DB_PATH` | `./data.db` | SQLite file path |
| `PORT` | `8000` | HTTP port |

## Railway Deploy
1. GitHub repo ဖန်တီး၊ ဒီ folder ကို push
2. Railway → New Project → Deploy from GitHub
3. Variables tab မှာ `ADMIN_PASSWORD`, `PUBLIC_BASE_URL`, `SECRET_KEY` ထည့်
4. Settings → Volume → Mount path: `/app` (database persist အတွက်)

## VPS Deploy (Docker)
```bash
docker build -t sublink-manager .
docker run -d -p 8000:8000 \
  -e ADMIN_PASSWORD=mysecret \
  -e PUBLIC_BASE_URL=https://sub.yourdomain.com \
  -v $(pwd)/data:/app \
  --name sublink sublink-manager
```

Nginx reverse proxy + Let's Encrypt နဲ့ HTTPS ထည့်ပါ။

## File Structure
```
sublink-manager/
├── main.py              # FastAPI app (1 file ထဲ)
├── requirements.txt
├── Dockerfile
├── templates/
│   ├── login.html
│   └── admin.html
└── static/
    └── style.css
```

ဒီ project က **Lovable, Supabase, Cloudflare ဘာမှ မပါ**။ Pure Python + SQLite ။
