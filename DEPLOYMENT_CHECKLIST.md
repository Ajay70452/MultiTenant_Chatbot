# Deployment Checklist for T2-Chatbot-2.0

This checklist ensures that your application will work correctly in production.

## ✅ Pre-Deployment Verification

### 1. Environment Variables Configuration

**Critical:** Your `.env` file is in `.gitignore` (correct for security), but you need to set these variables in production:

#### Required Environment Variables:
```bash
# OpenAI API Key (CRITICAL - this is what we fixed today)
OPENAI_API_KEY=sk-proj-...

# Pinecone Configuration
PINECONE_API_KEY=pcsk_...
PINECONE_ENVIRONMENT=us-east-1

# Database Configuration (for production)
DB_USER=postgres
DB_PASSWORD=<your-production-password>
DB_NAME=dental_chatbot_prod
DB_HOST=db  # or your production DB host
DB_PORT=5432

# Security
ALLOWED_ORIGINS=http://localhost:3000,https://your-production-domain.com
SECRET_KEY=<generate-a-secure-key>
```

**How to set in production:**
- If using Docker Compose: Set in `docker-compose.yml` environment section
- If using AWS/Cloud: Set in service environment variables (ECS, Lambda, etc.)
- If using Kubernetes: Use ConfigMaps and Secrets

### 2. Code Changes We Made Today

✅ **Fixed OpenAI API Key Loading** (`src/core/config.py`)
- Changed `load_dotenv()` to use explicit path
- This ensures `.env` is found regardless of working directory

✅ **Added Clinic Name to AI Prompt**
- Updated `src/core/agent.py`, `src/core/prompts/clinical.py`, `src/api/clinical.py`
- AI now knows the clinic name (e.g., "Robeck Dental")

✅ **Mounted Static Files for Frontend**
- Updated `src/main.py` to serve `/frontends` directory
- Clinical UI accessible at: `http://localhost:8000/frontends/clinical-ui/index.html`

### 3. Frontend Deployment

Your frontend is currently on **port 3000** (separate dev server).

**For Production, you have 2 options:**

**Option A: Serve from Backend (Port 8000) - RECOMMENDED**
- Already configured! The static files are mounted in `src/main.py`
- URL: `http://your-domain.com/frontends/clinical-ui/index.html?permanent_token=xxx`
- No need for separate frontend server

**Option B: Separate Frontend Server (Port 3000)**
- Deploy clinical UI separately (nginx, Vercel, etc.)
- URL: `http://your-frontend.com/?api=http://your-backend.com/api/clinical&permanent_token=xxx`
- Remember to add frontend domain to `ALLOWED_ORIGINS`

### 4. Database Migration

Before first deployment, run migrations:
```bash
# Inside the container or on the server
alembic upgrade head
```

### 5. Access Tokens for Clients

Make sure your production database has clients with access tokens:
```sql
-- Verify clients exist
SELECT client_id, clinic_name, access_token FROM clients;

-- If needed, add access tokens
UPDATE clients SET access_token = 'secure-random-token-here' WHERE client_id = '...';
```

Use these scripts to generate access URLs:
```bash
# Generate permanent URLs
python generate_permanent_url.py

# Or for specific client
python generate_permanent_url.py "Robeck"
```

## 🐳 Docker Deployment

### Build and Run with Docker Compose:

```bash
# 1. Ensure .env file exists with production values
cp .env.example .env  # if you have one
nano .env  # Edit with production values

# 2. Build and start services
docker-compose up --build -d

# 3. Run database migrations (first time only)
docker-compose exec app alembic upgrade head

# 4. Verify services are running
docker-compose ps
docker-compose logs app

# 5. Test the API
curl http://localhost:8000/
curl http://localhost:8000/config
```

### Verify Deployment is Working:

1. **Check API Status:**
   ```bash
   curl http://localhost:8000/status
   ```
   Should return: `{"api_status": "ok", "db_status": "ok"}`

2. **Check Environment Variables:**
   ```bash
   curl http://localhost:8000/config
   ```
   Should return: `{"allowed_origins": "...", "openai_api_key_set": "Yes"}`

3. **Test Clinical UI:**
   - Generate access URL: `python generate_permanent_url.py`
   - Open URL in browser
   - Ask: "What is the name of our clinic?"
   - Should respond with correct clinic name

## 🔒 Security Checklist

- [ ] `.env` file NOT committed to git (verify with `git status`)
- [ ] Production `.env` has strong passwords
- [ ] `SECRET_KEY` is randomly generated
- [ ] `ALLOWED_ORIGINS` includes only your domains
- [ ] Access tokens are secure random strings
- [ ] Database not exposed to public internet (no ports exposed in docker-compose.yml)
- [ ] HTTPS enabled in production (use reverse proxy like nginx)

## 📝 Production Environment Variables Template

Create this in your production environment:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE

# Pinecone
PINECONE_API_KEY=pcsk_YOUR_KEY_HERE
PINECONE_ENVIRONMENT=us-east-1

# Database
DB_USER=postgres
DB_PASSWORD=STRONG_PASSWORD_HERE
DB_NAME=dental_chatbot_prod
DB_HOST=db
DB_PORT=5432

# CORS
ALLOWED_ORIGINS=https://your-domain.com,https://frontend.your-domain.com

# Security
SECRET_KEY=GENERATE_RANDOM_SECRET_KEY_HERE
```

## 🚨 Common Deployment Issues & Fixes

### Issue 1: "No OPENAI_API_KEY" error
**Fix:** Verify environment variable is set in docker-compose.yml or cloud service
```bash
# Check inside container
docker-compose exec app env | grep OPENAI_API_KEY
```

### Issue 2: Frontend shows "Not Found"
**Fix:** Ensure `frontends/` directory is included in Docker image
```bash
# Verify frontends directory exists in container
docker-compose exec app ls -la /app/frontends
```

### Issue 3: "No access token provided"
**Fix:** Generate access URLs with permanent tokens
```bash
docker-compose exec app python generate_permanent_url.py
```

### Issue 4: Database connection fails
**Fix:** Check database service is healthy
```bash
docker-compose logs db
docker-compose exec db pg_isready -U postgres
```

### Issue 5: AI doesn't know clinic name
**Fix:** Already fixed in code! Make sure you deployed the latest code.

## 📊 Monitoring in Production

**Log Access:**
```bash
# View application logs
docker-compose logs -f app

# View database logs
docker-compose logs -f db

# View logs from web UI
http://your-domain.com/view-logs
```

**Health Checks:**
- API Status: `GET /status`
- Config Check: `GET /config`
- RAG Health: Check logs for "RAG context retrieved successfully"

## 🔄 Updating Production

When deploying updates:
```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild and restart
docker-compose down
docker-compose up --build -d

# 3. Run any new migrations
docker-compose exec app alembic upgrade head

# 4. Verify
curl http://localhost:8000/status
```

## ✅ Final Verification

Before going live, verify:
- [ ] Backend responds on port 8000
- [ ] Database is accessible and has clients
- [ ] OpenAI API key is working (`/config` shows "Yes")
- [ ] Frontend is accessible (either via port 8000 or separate server)
- [ ] Access tokens work (test a permanent URL)
- [ ] AI knows the clinic name
- [ ] RAG system retrieves knowledge base content
- [ ] CORS is configured for your frontend domain

## 🆘 Need Help?

If deployment fails, check:
1. `docker-compose logs app` for application errors
2. `docker-compose logs db` for database errors
3. `/view-logs` endpoint for runtime logs
4. Run `python generate_permanent_url.py` to test database connectivity
