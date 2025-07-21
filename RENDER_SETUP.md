# TGL MEDUSA - Render.com Setup Guide

## 🚀 Quick Deployment Steps

### 1. **Create Render Account & Connect Repository**
1. Sign up at [render.com](https://render.com)
2. Connect your GitHub account
3. Select repository: `Wisyle/combologger`
4. Branch: `devin/1737478987-crypto-bot-monitoring-system`

### 2. **Deploy Using Blueprint**
1. **Create New → Blueprint**
2. **Select repository**: `Wisyle/combologger`
3. **Blueprint file**: `render.yaml` (automatically detected)
4. **Review services**: 
   - `tgl-medusa-loggers-web` (Web service)
   - `tgl-medusa-loggers-worker` (Background worker)
   - `tgl-medusa-db` (PostgreSQL database)
5. **Deploy**

### 3. **Environment Variables Configuration**

#### **Automatic Variables** (configured in render.yaml)
- ✅ `DATABASE_URL` - Auto-configured from PostgreSQL database
- ✅ `SECRET_KEY` - Auto-generated secure key
- ✅ `ALGORITHM` - Set to HS256
- ✅ `ACCESS_TOKEN_EXPIRE_MINUTES` - Set to 30
- ✅ `APP_NAME` - Set to "TGL MEDUSA"
- ✅ `DEBUG` - Set to false
- ✅ `ENVIRONMENT` - Set to production

#### **Optional Variables** (set in Render Dashboard)
Navigate to your web service → **Environment** tab and add:

```bash
# Default Admin Account (optional)
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_ADMIN_PASSWORD=SecurePassword123!

# Default Telegram Settings (optional)
DEFAULT_TELEGRAM_BOT_TOKEN=your-bot-token-here
DEFAULT_TELEGRAM_CHAT_ID=your-chat-id-here
DEFAULT_TELEGRAM_TOPIC_ID=your-topic-id-here
```

### 4. **Generate Secure Secret Key** (if needed manually)
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 5. **Post-Deployment Setup**
1. **Access your app**: `https://your-app-name.onrender.com`
2. **Register admin user**: `/register`
3. **Setup 2FA**: Scan QR code with Google Authenticator
4. **Create bot instances**: Add your exchange API keys
5. **Test notifications**: Verify Telegram messages reach correct topics

---

## 🔧 Environment Variable Strategy

### **Per Service vs Shared Configuration**

#### **Web Service** (`tgl-medusa-loggers-web`)
- All core application variables
- Database connection
- Authentication settings
- Optional admin defaults

#### **Worker Service** (`tgl-medusa-loggers-worker`)
- Inherits database connection
- Generates own SECRET_KEY for security
- Shares core application settings

#### **Database Service** (`tgl-medusa-db`)
- Automatically provides `DATABASE_URL` to other services
- Connection string format: `postgresql://user:pass@host:port/dbname`

---

## 🚨 Troubleshooting

### **Common Issues:**

#### 1. **YAML Syntax Errors**
```bash
# Validate locally before deployment
python validate_render_yaml.py
```

#### 2. **Database Connection Issues**
- Verify `DATABASE_URL` is properly set via `fromDatabase` reference
- Check PostgreSQL service is running
- Ensure migration runs during build: `python migration.py`

#### 3. **Authentication Problems**
- Verify `SECRET_KEY` is generated/set
- Check JWT token expiration settings
- Ensure 2FA setup works with Google Authenticator

#### 4. **Worker Service Not Starting**
- Check `worker.py` file exists and is executable
- Verify imports work: `from main import monitor_instances`
- Check worker logs in Render dashboard

#### 5. **Environment Variable Issues**
```bash
# Check if variables are properly set
echo $DATABASE_URL
echo $SECRET_KEY
```

---

## 📊 Service Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Service   │    │  Worker Service  │    │   PostgreSQL    │
│                 │    │                  │    │    Database     │
│ • FastAPI App   │    │ • Bot Monitoring │    │                 │
│ • Authentication│    │ • Telegram Msgs  │    │ • User Data     │
│ • Admin Panel   │    │ • Exchange APIs  │    │ • Bot Instances │
│ • REST API      │    │ • Change Detection│    │ • Polling State │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    Shared DATABASE_URL
```

---

## 🔐 Security Best Practices

### **Environment Variables**
- ✅ Use `generateValue: true` for secrets
- ✅ Never commit secrets to git
- ✅ Use Render's encrypted environment variables
- ✅ Rotate secrets regularly

### **Database Security**
- ✅ PostgreSQL with SSL connections
- ✅ Strong database passwords (auto-generated)
- ✅ Connection pooling enabled
- ✅ Regular automated backups

### **Application Security**
- ✅ JWT token expiration (30 minutes)
- ✅ 2FA with Google Authenticator
- ✅ HTTPS enforced (automatic on Render)
- ✅ Rate limiting enabled

---

## 📈 Monitoring & Maintenance

### **Health Checks**
- Web service: `https://your-app.onrender.com/api/health`
- Automatic restart on failures
- Uptime monitoring in Render dashboard

### **Logs**
- **Web service logs**: Request/response, authentication events
- **Worker logs**: Bot monitoring, Telegram notifications, API calls
- **Database logs**: Connection status, query performance

### **Scaling**
```yaml
# In render.yaml (if needed)
scaling:
  minInstances: 1
  maxInstances: 3
  targetCPUPercent: 70
```

---

## 🎯 Next Steps After Deployment

1. **Test authentication flow** - Register, login, setup 2FA
2. **Create test bot instance** - Add exchange API keys
3. **Verify Telegram notifications** - Check topic-specific messages
4. **Monitor performance** - Check logs and health endpoints
5. **Setup custom domain** (optional) - Configure DNS and SSL

**Ready to deploy? Follow the steps above and your TGL MEDUSA will be live! 🚀**
