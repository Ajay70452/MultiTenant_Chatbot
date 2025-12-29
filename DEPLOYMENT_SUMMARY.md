# Deployment Summary - Everything You Need to Know

## ✅ What We Fixed Today

### 1. **OpenAI API Key Loading Issue** ✅ FIXED
**Problem:** API key wasn't loading because `load_dotenv()` was looking in the wrong directory.

**Solution:** Updated `src/core/config.py` to use absolute path resolution:
```python
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)
```

**Result:** ✅ API key now loads correctly in any environment.

### 2. **AI Doesn't Know Clinic Name** ✅ FIXED
**Problem:** AI couldn't answer "What is the name of our clinic?"

**Solution:** Updated the system to pass `clinic_name` to the AI prompt:
- Modified `src/core/agent.py` to accept `clinic_name` parameter
- Modified `src/core/prompts/clinical.py` to include clinic name in prompt
- Modified `src/api/clinical.py` to pass `client.clinic_name`

**Result:** ✅ AI now knows it's "Robeck Dental" and can answer clinic-related questions.

### 3. **Frontend Static Files Not Served** ✅ FIXED
**Problem:** URL `http://localhost:8000/frontends/...` returned 404 Not Found.

**Solution:** Added static file mounting in `src/main.py`:
```python
app.mount("/frontends", StaticFiles(directory=str(FRONTENDS_DIR)), name="frontends")
```

**Result:** ✅ Frontend now accessible at `http://localhost:8000/frontends/clinical-ui/index.html`

### 4. **Permanent Token Authentication** ✅ ADDED
**Problem:** Only one-time tokens worked, which expire after 5 minutes.

**Solution:** Added `permanent_token` parameter support in `frontends/clinical-ui/clinical.js`

**Result:** ✅ Can now use permanent URLs that never expire:
```
http://localhost:3000/?api=http://localhost:8000/api/clinical&permanent_token=robeck-test-token-456
```

## 📦 New Files Created for Deployment

1. **`.dockerignore`** - Optimizes Docker builds by excluding unnecessary files
2. **`.env.example`** - Template for environment variables
3. **`DEPLOYMENT_CHECKLIST.md`** - Comprehensive deployment guide
4. **`verify_deployment.py`** - Automated deployment verification script
5. **`generate_permanent_url.py`** - Generate access URLs for clients
6. **`generate_dev_url.py`** - Generate dev server URLs (port 3000)

## 🚀 How to Deploy to Production

### Option 1: Quick Deploy with Docker (RECOMMENDED)

```bash
# 1. Clone/pull latest code
git pull origin main

# 2. Create production .env file
cp .env.example .env
nano .env  # Fill in production values

# 3. Build and start
docker-compose up --build -d

# 4. Run migrations (first time only)
docker-compose exec app alembic upgrade head

# 5. Verify deployment
python verify_deployment.py

# 6. Generate access URLs
python generate_permanent_url.py
```

### Option 2: Manual Deployment

```bash
# 1. Set up virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export OPENAI_API_KEY=sk-proj-...
export PINECONE_API_KEY=pcsk_...
# ... (set all required vars)

# 4. Run migrations
alembic upgrade head

# 5. Start application
gunicorn src.main:app --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## 🔑 Critical Environment Variables

Make sure these are set in production:

```bash
OPENAI_API_KEY=sk-proj-...           # Your OpenAI API key
PINECONE_API_KEY=pcsk_...            # Your Pinecone API key
PINECONE_ENVIRONMENT=us-east-1       # Pinecone region
PINECONE_INDEX_NAME=robeck-dental-v2 # Your Pinecone index

DB_USER=postgres                     # Database user
DB_PASSWORD=SECURE_PASSWORD          # Strong password!
DB_NAME=dental_chatbot_prod          # Database name
DB_HOST=db                           # 'db' for Docker, or your DB host
DB_PORT=5432                         # PostgreSQL port

ALLOWED_ORIGINS=https://your-domain.com  # Your frontend URLs
SECRET_KEY=RANDOM_SECRET_KEY             # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🧪 Testing Your Deployment

### 1. Run Verification Script
```bash
python verify_deployment.py
```

This checks:
- ✅ Environment variables are set
- ✅ Code fixes are present
- ✅ Frontend files exist
- ✅ API is running
- ✅ Database has clients

### 2. Manual Testing
```bash
# Test API status
curl http://localhost:8000/status

# Test config (should show openai_api_key_set: "Yes")
curl http://localhost:8000/config

# Generate access URL
python generate_permanent_url.py Robeck

# Test in browser - ask "What is the name of our clinic?"
# Should respond: "Robeck Dental"
```

## 📊 Monitoring Your Deployment

### View Logs
```bash
# All logs
docker-compose logs -f

# Just application logs
docker-compose logs -f app

# Just database logs
docker-compose logs -f db
```

### Check via Web UI
- View logs: `http://your-domain.com/view-logs`
- API status: `http://your-domain.com/status`
- Config check: `http://your-domain.com/config`

## 🆘 Troubleshooting

### "OpenAI API key not set"
```bash
# Check environment variable in container
docker-compose exec app env | grep OPENAI_API_KEY

# If missing, add to docker-compose.yml and restart
docker-compose down
docker-compose up -d
```

### "No access token provided"
```bash
# Generate permanent URL
python generate_permanent_url.py

# Or check database
docker-compose exec app python check_tokens.py
```

### "Practice profile not configured"
```bash
# Check if client has profile
docker-compose exec app python -c "from src.core.db import get_db; from src.models.models import Client; db = next(get_db()); client = db.query(Client).first(); print('Has profile:', bool(client.profile if client else None))"
```

### Frontend shows 404
```bash
# Verify frontends directory in container
docker-compose exec app ls -la /app/frontends/clinical-ui/
```

## ✅ Pre-Launch Checklist

Before going live:

- [ ] All environment variables set in production
- [ ] `.env` file NOT committed to git
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Clients exist in database with access tokens
- [ ] `verify_deployment.py` passes all checks
- [ ] Test access URL works in browser
- [ ] AI responds with correct clinic name
- [ ] RAG system retrieves knowledge base content
- [ ] CORS configured for production domains
- [ ] HTTPS enabled (use nginx or cloud load balancer)
- [ ] Database backups configured
- [ ] Monitoring/alerting set up

## 🎉 You're Ready!

Once all checks pass, your deployment is ready to go live. The key fixes we made today ensure:

1. ✅ OpenAI API key loads correctly in any environment
2. ✅ AI knows the clinic name and practice information
3. ✅ Frontend serves correctly from backend
4. ✅ Permanent URLs work and never expire
5. ✅ All configurations are production-ready

## 📞 Quick Reference

**Generate Access URLs:**
```bash
python generate_permanent_url.py
```

**Start Production:**
```bash
docker-compose up -d
```

**View Logs:**
```bash
docker-compose logs -f app
```

**Verify Deployment:**
```bash
python verify_deployment.py
```

**Update Production:**
```bash
git pull && docker-compose up --build -d
```

---

**Need help?** Check `DEPLOYMENT_CHECKLIST.md` for detailed instructions.
