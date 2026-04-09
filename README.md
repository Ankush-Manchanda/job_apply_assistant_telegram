# Telegram-Enabled 24/7 Job Apply Assistant

This is a cloud-ready FastAPI project that:
- checks job feeds at fixed intervals
- filters jobs using your criteria
- sends Telegram notifications to your phone
- runs 24/7 on Render or Railway
- lets you open a dashboard, pick a resume, and review the job link before applying

## Honest limitations
- This project is built for **job discovery, filtering, Telegram alerts, tracking, and assisted apply**.
- It does **not** try to mass-submit applications to third-party portals in the background. Job sites change frequently and often restrict automation.
- The 24/7 cloud part is stable. The "final click" still belongs to you.

## Main features
- Telegram alerts for matched jobs
- Scheduled polling every N minutes
- RSS job sources + simple HTML source support
- Resume library
- Match scoring engine
- Dashboard with job list, filters, status tracking
- Mark as applied / skipped / saved
- Open apply link from dashboard

## Setup

### 1) Create Telegram bot
1. Open Telegram and search `@BotFather`
2. Create a bot with `/newbot`
3. Copy the bot token
4. Message your bot once from your Telegram account
5. Open this URL in browser after replacing your token:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
6. Find your `chat.id`

### 2) Local run
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # on Windows
# or cp .env.example .env on Linux/macOS

uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000`

### 3) Render deployment
1. Push this folder to GitHub
2. Create a new Render web service from the repo
3. Render will detect `render.yaml`
4. Set these environment variables:
   - `APP_BASE_URL` = your Render URL, for example `https://job-apply-assistant.onrender.com`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `SECRET_KEY`
   - `JOB_CHECK_INTERVAL_MINUTES`
5. Deploy

## Default sources included
The project ships with sample sources. Update them from the dashboard or directly in database:
- RemoteOK RSS
- We Work Remotely RSS
- Any RSS feed from companies or job aggregators
- Basic HTML page source using CSS selector or pattern matching

## Important note about resumes on cloud
Resumes uploaded to the deployed app remain on the server storage. On free/shared plans, storage may be ephemeral. For long-term use:
- use a paid persistent disk, or
- store resume metadata in DB and keep files in object storage

## Project structure
```text
job_apply_assistant_telegram/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   ├── templates/
│   └── static/
├── resumes/
├── uploads/
├── storage/
├── requirements.txt
├── render.yaml
└── README.md
```

## Recommended filters for you
- Titles: Data Analyst, Business Analyst, Reporting Analyst, BI Analyst, Analyst Intern, MIS Analyst
- Locations: Gurugram, Noida, Delhi NCR, Remote
- Skills: Excel, SQL, Power BI, Python
- Exclude: unpaid, commission, sales, field work, 3+ years

## Security notes
- Change `SECRET_KEY`
- Do not commit real bot token or personal files
- Review job sources before trusting them
