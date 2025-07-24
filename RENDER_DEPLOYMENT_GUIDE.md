# TAR Global Strategies Dashboard - Render Deployment Guide

## 🚀 **AUTOMATIC DATABASE MIGRATION SYSTEM**

The application now includes an **automatic migration system** that runs on every deployment startup. This ensures your PostgreSQL database on Render is properly configured without manual intervention.

---

## 📋 **DEPLOYMENT STEPS**

### **Step 1: Connect Your Repository**
1. Login to [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select the repository containing your TAR Dashboard code

### **Step 2: Configure the Service**
- **Name**: `tar-global-strategies-dashboard`
- **Environment**: `Python`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Auto-Deploy**: ✅ Enabled

### **Step 3: Add Required Environment Variables**
```env
# Database (will be auto-configured by Render PostgreSQL)
DATABASE_URL=postgresql://[auto-generated-by-render]

# Security Keys (generate secure values)
SECRET_KEY=[generate-random-string]
JWT_SECRET=[generate-random-string]

# Optional: Telegram Integration
DEFAULT_TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DEFAULT_TELEGRAM_CHAT_ID=your_telegram_chat_id

# Application Settings
DEBUG=false
HOST=0.0.0.0
PORT=10000
```

### **Step 4: Create PostgreSQL Database**
1. In Render Dashboard → **"New +"** → **"PostgreSQL"**
2. **Name**: `tar-dashboard-db`
3. **Database Name**: `tar_dashboard`
4. **User**: `tar_admin`
5. **Region**: Choose closest to your users

### **Step 5: Link Database to Web Service**
1. Go to your web service **Environment** tab
2. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Link to your PostgreSQL database

### **Step 6: Deploy**
1. Click **"Deploy Latest Commit"**
2. Watch the build logs for successful migration messages
3. Application will be available at your Render URL

---

## 🔧 **AUTOMATIC MIGRATION FEATURES**

### **What Happens on Deployment:**
✅ **Database Connection**: Verifies PostgreSQL connection  
✅ **Table Creation**: Creates all required tables automatically  
✅ **Schema Fixes**: Adds missing columns (like `user_id` in `api_credentials`)  
✅ **User Creation**: Creates default admin user if none exists  
✅ **Data Migration**: Fixes existing records to match new schema  
✅ **Verification**: Validates all migrations completed successfully  

### **Migration Log Messages:**
```
🚀 Starting automatic deployment migrations...
📊 Database type: PostgreSQL
📋 Creating base tables...
🔍 Checking users table...
✅ users table already exists
🔍 Checking api_credentials table schema...
➕ Adding user_id column to api_credentials...
✅ Added user_id column
✅ Added foreign key constraint
🔍 Checking for default admin user...
➕ Creating default admin user...
✅ Created default admin user
🔑 Default login: admin@tarstrategies.com / admin123
⚠️  CHANGE DEFAULT PASSWORD AFTER FIRST LOGIN!
🎉 All deployment migrations completed successfully!
```

---

## 🔐 **DEFAULT ACCESS CREDENTIALS**

### **First-Time Login:**
- **URL**: `https://your-app-name.onrender.com`
- **Email**: `admin@tarstrategies.com`
- **Password**: `admin123`

### **⚠️ SECURITY IMPORTANT:**
1. **Change default password immediately after first login**
2. **Enable 2FA for enhanced security**
3. **Create additional user accounts with appropriate roles**
4. **Update SECRET_KEY and JWT_SECRET environment variables**

---

## 📊 **MONITORING DEPLOYMENT**

### **Build Logs to Watch For:**
✅ **Successful Migration**: `🎉 All deployment migrations completed successfully!`  
✅ **Server Start**: `INFO: Application startup complete.`  
✅ **Database Connection**: `✅ Database connection successful`  

### **Common Issues & Solutions:**

#### **Migration Fails:**
```
❌ Database migrations failed! Application cannot start.
```
**Solution**: Check DATABASE_URL is correctly configured and PostgreSQL is accessible

#### **User Creation Fails:**
```
❌ Failed to create default admin user
```
**Solution**: Ensure users table was created successfully, check PostgreSQL permissions

#### **Foreign Key Constraint Error:**
```
⚠️  Could not add foreign key constraint: [error]
```
**Solution**: This is usually harmless - constraint may already exist from previous deployment

---

## 🌍 **ENVIRONMENT VARIABLES REFERENCE**

### **Required:**
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | Application secret key | `your-secret-key-here` |
| `JWT_SECRET` | JWT token signing key | `your-jwt-secret-here` |

### **Optional:**
| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | None |
| `DEFAULT_TELEGRAM_CHAT_ID` | Default Telegram chat ID | None |
| `DEBUG` | Enable debug mode | `false` |
| `HOST` | Server host binding | `0.0.0.0` |
| `PORT` | Server port | `10000` |

---

## 🧪 **TESTING LOCALLY BEFORE DEPLOYMENT**

Run the test script to verify migrations work:
```bash
python test_deployment_migration.py
```

Expected output:
```
🧪 Testing deployment migration system...
✅ Database connection successful
🎉 Migration test completed successfully!
✅ Default admin user login test successful
🎉 All deployment tests passed!
✅ Your application is ready for Render deployment
```

---

## 🔄 **UPDATING YOUR DEPLOYMENT**

### **For Code Updates:**
1. Push changes to your GitHub repository
2. Render automatically rebuilds and redeploys
3. Migrations run automatically on startup
4. No manual database changes needed

### **For Database Schema Changes:**
1. Update your SQLAlchemy models in the code
2. The automatic migration system handles most changes
3. For complex migrations, add logic to `startup_migration.py`

---

## 📞 **SUPPORT & TROUBLESHOOTING**

### **Render Dashboard Access:**
- **Service Logs**: Monitor real-time application logs
- **Events**: Track deployments and service events  
- **Metrics**: Monitor CPU, memory, and request metrics

### **Database Management:**
- **Render PostgreSQL Dashboard**: Monitor database performance
- **Connection**: Test database connectivity
- **Backups**: Automatic daily backups included

### **Common URLs:**
- **Dashboard**: `https://your-app-name.onrender.com`
- **Health Check**: `https://your-app-name.onrender.com/api/health`
- **API Documentation**: `https://your-app-name.onrender.com/docs`

---

## 🎉 **DEPLOYMENT COMPLETE**

Once deployed, your TAR Global Strategies Dashboard will be accessible with:

✅ **Automatic Database Migrations**  
✅ **Real-time Trading Bot Monitoring**  
✅ **DEX Arbitrage Tracking**  
✅ **Validator Node Management**  
✅ **System Health Monitoring**  
✅ **Secure Authentication & 2FA**  
✅ **Professional TAR Global Strategies Branding**

**🚀 Your advanced crypto monitoring dashboard is now live on Render!** 