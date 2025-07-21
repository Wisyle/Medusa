# TGL Medusa Loggers - Deployment Guide

## 🚀 Recommended Hosting Platforms

### 1. **Render.com** (⭐ RECOMMENDED)
**Best for**: Production deployments with automatic scaling
- ✅ **Free tier available** with 750 hours/month
- ✅ **Automatic HTTPS** and custom domains
- ✅ **PostgreSQL database** included
- ✅ **Environment variables** management
- ✅ **Auto-deploy** from GitHub
- ✅ **Background services** for bot polling

**Pricing**: Free tier → $7/month for production

### 2. **Railway.app** 
**Best for**: Developer-friendly deployments
- ✅ **$5 free credit** monthly
- ✅ **PostgreSQL/Redis** add-ons
- ✅ **Simple configuration**
- ✅ **GitHub integration**

**Pricing**: Pay-as-you-go, ~$5-15/month

### 3. **DigitalOcean App Platform**
**Best for**: Scalable production with more control
- ✅ **$5/month** basic tier
- ✅ **Managed databases**
- ✅ **Load balancing**
- ✅ **Custom domains**

**Pricing**: $5-12/month

### 4. **Heroku** (Legacy Option)
**Best for**: Quick prototypes (limited free tier)
- ⚠️ **No free tier** anymore
- ✅ **Easy deployment**
- ✅ **Add-ons ecosystem**

**Pricing**: $7/month minimum

---

## 📋 Pre-Deployment Checklist

### 1. **Environment Variables Setup**
Create these environment variables in your hosting platform:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname
# OR for SQLite (development only)
DATABASE_URL=sqlite:///./tgl_medusa.db

# Security
SECRET_KEY=your-super-secret-jwt-key-here-64-chars-minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
APP_NAME=TGL Medusa Loggers
DEBUG=false
ENVIRONMENT=production

# Default Admin (optional)
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_ADMIN_PASSWORD=SecurePassword123!

# Telegram (optional defaults)
DEFAULT_TELEGRAM_BOT_TOKEN=your-default-bot-token
DEFAULT_TELEGRAM_CHAT_ID=your-default-chat-id
DEFAULT_TELEGRAM_TOPIC_ID=your-default-topic-id
```

### 2. **Database Migration**
The app includes automatic migration on startup, but for production:

```bash
# Run migration manually (optional)
python migration.py
```

### 3. **Dependencies Check**
Ensure `requirements.txt` includes all dependencies:
```
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
python-jose[cryptography]>=3.3.0
passlib>=1.7.4
pyotp>=2.9.0
qrcode>=7.4.0
ccxt>=4.0.0
python-telegram-bot>=20.0
# ... (see full requirements.txt)
```

---

## 🔧 Platform-Specific Deployment Instructions

### **Option 1: Render.com Deployment** (RECOMMENDED)

#### Step 1: Prepare Repository
```bash
# Ensure you're on the correct branch
git checkout devin/1737478987-crypto-bot-monitoring-system
git push origin devin/1737478987-crypto-bot-monitoring-system
```

#### Step 2: Create render.yaml
```yaml
services:
  - type: web
    name: tgl-medusa-loggers
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: tgl-medusa-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ENVIRONMENT
        value: production
      - key: DEBUG
        value: false

databases:
  - name: tgl-medusa-db
    databaseName: tgl_medusa_loggers
    user: tgl_user
```

#### Step 3: Deploy on Render
1. **Sign up** at [render.com](https://render.com)
2. **Connect GitHub** repository
3. **Create New → Blueprint**
4. **Select repository**: `Wisyle/combologger`
5. **Branch**: `devin/1737478987-crypto-bot-monitoring-system`
6. **Blueprint file**: `render.yaml`
7. **Deploy**

#### Step 4: Configure Environment Variables
In Render dashboard:
1. Go to **Environment** tab
2. Add required variables (see checklist above)
3. **Save Changes**

### **Option 2: Railway.app Deployment**

#### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

#### Step 2: Deploy
```bash
cd /path/to/combologger
railway init
railway add postgresql
railway deploy
```

#### Step 3: Set Environment Variables
```bash
railway variables set SECRET_KEY=your-secret-key
railway variables set ENVIRONMENT=production
railway variables set DEBUG=false
```

### **Option 3: DigitalOcean App Platform**

#### Step 1: Create App Spec
```yaml
name: tgl-medusa-loggers
services:
- name: web
  source_dir: /
  github:
    repo: Wisyle/combologger
    branch: devin/1737478987-crypto-bot-monitoring-system
  run_command: uvicorn main:app --host 0.0.0.0 --port $PORT
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: SECRET_KEY
    value: your-secret-key
  - key: ENVIRONMENT
    value: production

databases:
- name: tgl-medusa-db
  engine: PG
  version: "13"
```

#### Step 2: Deploy
1. **Login** to DigitalOcean
2. **Apps → Create App**
3. **Upload app spec** or connect GitHub
4. **Review and deploy**

---

## 🔒 Security Configuration

### 1. **SSL/HTTPS**
- ✅ **Render/Railway**: Automatic HTTPS
- ✅ **DigitalOcean**: Automatic HTTPS
- ⚠️ **Custom domains**: Configure DNS properly

### 2. **Environment Variables**
```bash
# Generate secure secret key
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Use this output as SECRET_KEY
```

### 3. **Database Security**
- ✅ Use **PostgreSQL** in production (not SQLite)
- ✅ Enable **connection pooling**
- ✅ Set **strong passwords**
- ✅ Enable **SSL connections**

### 4. **API Security**
- ✅ **Rate limiting** (built into FastAPI)
- ✅ **CORS configuration** (already configured)
- ✅ **JWT token expiration** (30 minutes default)

---

## 📊 Monitoring & Maintenance

### 1. **Health Checks**
Your app includes health endpoint: `https://your-domain.com/api/health`

### 2. **Logging**
```python
# Application logs are automatically captured
# Check platform-specific log viewers:
# - Render: Logs tab in dashboard
# - Railway: railway logs
# - DigitalOcean: Runtime logs
```

### 3. **Database Backups**
- **Render**: Automatic PostgreSQL backups
- **Railway**: Manual backup commands
- **DigitalOcean**: Automatic daily backups

### 4. **Scaling**
```yaml
# For high-traffic scenarios
instance_count: 3  # Multiple instances
instance_size_slug: basic-s  # Larger instances
```

---

## 🚨 Troubleshooting

### Common Issues:

#### 1. **Database Connection Errors**
```bash
# Check DATABASE_URL format
postgresql://username:password@host:port/database_name

# Verify database is running
# Check environment variables are set correctly
```

#### 2. **Authentication Issues**
```bash
# Verify SECRET_KEY is set and consistent
# Check JWT token expiration settings
# Ensure TOTP secret generation works
```

#### 3. **Telegram Notifications**
```bash
# Verify bot tokens are valid
# Check chat IDs and topic IDs
# Test with simple message first
```

#### 4. **Static Files (if needed)**
```bash
# For production static file serving
pip install whitenoise
# Add to main.py if needed
```

---

## 🎯 Post-Deployment Steps

### 1. **Create Admin User**
```bash
# Access your deployed app
https://your-app-domain.com/register

# Register first admin user
# Setup 2FA with Google Authenticator
```

### 2. **Configure Bot Instances**
1. **Login** to admin panel
2. **Create bot instances** with your exchange API keys
3. **Set Telegram tokens** and topic IDs
4. **Start monitoring**

### 3. **Test Notifications**
1. **Create test bot instance**
2. **Verify Telegram notifications** reach correct topics
3. **Check polling functionality**

### 4. **Domain Setup** (Optional)
```bash
# Custom domain configuration
# 1. Add CNAME record: your-domain.com → your-app.render.com
# 2. Configure in platform dashboard
# 3. Wait for SSL certificate generation
```

---

## 💡 Performance Optimization

### 1. **Database Optimization**
```python
# Connection pooling (already configured)
# Index optimization for frequent queries
# Regular VACUUM for PostgreSQL
```

### 2. **Caching** (Optional)
```bash
# Add Redis for session caching
pip install redis
# Configure in environment variables
```

### 3. **CDN** (For static assets)
```bash
# Use platform CDN or external CDN
# Configure static file serving
```

---

## 📞 Support & Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://docs.railway.app/
- **DigitalOcean Docs**: https://docs.digitalocean.com/products/app-platform/

---

## 🔄 Continuous Deployment

### GitHub Actions (Optional)
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Deploy to Render
      # Platform-specific deployment action
```

**Ready to deploy? Choose your platform and follow the specific instructions above!** 🚀
