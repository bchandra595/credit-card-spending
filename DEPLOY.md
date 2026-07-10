# Publishing the Spending Analyzer

## Privacy before you deploy

This app processes **financial statements**. If you publish a public URL:

- Users' PDF/CSV data will be processed on **whatever server hosts the app**
- For a **public** deployment, add authentication and use HTTPS
- Keep **online merchant lookup off by default** (already the default) so merchant names are not sent to DuckDuckGo unless the user opts in
- Never commit `.cache/`, uploaded files, or API secrets to Git

**Local use (current setup):** everything stays on your computer. No statement data is sent to the internet unless online lookup is enabled.

---

## Option 1: Streamlit Community Cloud (easiest, free tier)

**What you need:**
- GitHub account
- This repo pushed to GitHub (only the `credit-card-spending/` folder or whole repo)
- `requirements.txt` (already included)
- `app.py` as the entry point

**Steps:**

1. Push code to GitHub:
   ```bash
   cd credit-card-spending
   git add .
   git commit -m "Add credit card spending analyzer"
   git push origin main
   ```

2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub

3. Click **New app** → select your repo

4. Set **Main file path:** `credit-card-spending/app.py`

5. Click **Deploy** — you get a URL like `https://your-app.streamlit.app`

**Optional:** add `packages.txt` if you need system libraries (not required for this app).

---

## Option 2: Docker (AWS, GCP, Railway, Fly.io)

**What you need:**
- Dockerfile (see below)
- Container registry or platform account
- Domain + TLS certificate (platforms often provide this)

**Example Dockerfile:**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Run locally:**
```bash
docker build -t spending-analyzer .
docker run -p 8501:8501 spending-analyzer
```

Deploy the image to Railway, Fly.io, AWS ECS, Google Cloud Run, etc.

---

## Option 3: Single VPS (DigitalOcean, Linode)

1. Rent a small Linux server
2. Install Python 3.11+, clone the repo
3. Run behind **nginx** reverse proxy with **Let's Encrypt** SSL
4. Use **systemd** or **supervisor** to keep Streamlit running:

   ```bash
   streamlit run app.py --server.port 8501 --server.address 127.0.0.1
   ```

5. Add **HTTP basic auth** or **OAuth** at the nginx layer — Streamlit has no built-in login

---

## Checklist for a production URL

| Item | Why |
|------|-----|
| HTTPS | Encrypt data in transit |
| Authentication | Statements are sensitive |
| Private repo or secrets manager | Don't expose credentials |
| `.gitignore` for `.cache/` | Don't leak merchant lookup cache |
| Resource limits | Large PDFs need ~512MB+ RAM |
| Terms / privacy notice | Tell users data is processed on your server |

---

## Multi-page app entry

Streamlit discovers:
- `app.py` — Spending Analyzer (home)
- `pages/1_PDF_to_CSV.py` — PDF converter

Both deploy together when `app.py` is the main file.

---

## Environment variables (optional future)

If you later add paid APIs (OpenAI, etc.):

```bash
OPENAI_API_KEY=sk-...
```

Set these in Streamlit Cloud → **Settings → Secrets**, not in code.
