# TAR Global Strategies Dashboard - Multi-Service Render Deployment

## 🚀 **MULTI-SERVICE ARCHITECTURE**

The TAR Global Strategies Dashboard now deploys as **4 separate services** on Render for optimal performance and scalability:

1. **🌐 Web Service** - Main dashboard and API endpoints
2. **⚙️ Worker Service** - Background polling and monitoring 
3. **📊 Strategy Monitor Service** - Strategic analysis and reporting
4. **🗄️ PostgreSQL Database** - Centralized data storage

Each service runs independently with automatic restarts and scaling.

---

## 📋 **RENDER DEPLOYMENT STEPS**

### **Step 1: Push Your Code to GitHub**
Ensure all your code is committed and pushed:
```bash
git add .
git commit -m "Ready for multi-service deployment"
git push origin master
```

### **Step 2: Connect Repository to Render**
1. Login to [render.com](https://render.com)
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Select the repository containing your TAR Dashboard code
5. **Render will automatically detect the `render.yaml` and create all services**

### **📋 What You'll See During Deployment:**
- **Environment Variables**: Only required ones (DATABASE_URL, SECRET_KEY, etc.)
- **No Telegram prompts**: Telegram is configured per instance in dashboard
- **4 Services Created**: Web, Worker, Strategy Monitor, Database
- **Auto-Generated Secrets**: Render creates secure keys automatically
- **⚠️ Plan Requirement**: Starter plan needed for worker services (~$7/month per service)

### **Step 3: Services Created Automatically**

Render will create these services from your `render.yaml`:

#### 🌐 **tar-dashboard-web** 
- **Type**: Web Service
- **Plan**: Starter (supports background workers)
- **Purpose**: Main dashboard UI and API
- **URL**: `https://tar-dashboard-web.onrender.com`
- **Health Check**: `/api/health`

#### ⚙️ **tar-dashboard-worker**
- **Type**: Worker Service  
- **Plan**: Starter (required for worker services)
- **Purpose**: Background polling of exchanges
- **Command**: `python worker.py`

#### 📊 **tar-dashboard-strategy-monitor**
- **Type**: Worker Service
- **Plan**: Starter (required for worker services)
- **Purpose**: Strategy analysis and monitoring
- **Command**: `python init_strategy_monitor.py && python strategy_monitor_worker.py`

#### 🗄️ **tar-dashboard-db**
- **Type**: PostgreSQL Database
- **Plan**: Starter
- **Database**: `tar_dashboard`
- **User**: `tar_admin`

### **Step 4: Monitor Deployment**

Watch the deployment logs for each service:

#### **Web Service Logs:**
```
🚀 Starting automatic deployment migrations...
📊 Database type: PostgreSQL
✅ Created default admin user
🎉 All deployment migrations completed successfully!
INFO: Application startup complete.
```

#### **Worker Service Logs:**
```
INFO: Starting background worker...
INFO: Polling instances initialized
INFO: Worker ready for polling tasks
```

#### **Strategy Monitor Logs:**
```
INFO: Initializing strategy monitors...
INFO: Strategy monitor worker started
INFO: Monitoring 0 active strategies
```

---

## 🔧 **AUTOMATIC FEATURES**

### **✅ Database Auto-Migration**
The web service automatically:
- Creates all required tables
- Adds missing columns (`user_id` in `api_credentials`)
- Creates default admin user
- Sets up proper foreign key relationships

### **✅ Service Communication**
All services share the same PostgreSQL database and communicate via:
- Shared database state
- Real-time polling updates
- Strategy monitoring coordination

### **✅ Environment Variables**
All services automatically receive:
- `DATABASE_URL` - Linked to PostgreSQL database
- `SECRET_KEY` & `JWT_SECRET` - Auto-generated secure keys
- **No Telegram tokens needed** - Configure per instance in dashboard
- Production configuration settings

---

## 🔐 **FIRST-TIME ACCESS**

### **Default Login Credentials:**
- **URL**: `https://tar-dashboard-web.onrender.com`
- **Email**: `admin@tarstrategies.com`  
- **Password**: `admin123`

### **⚠️ IMMEDIATE SECURITY STEPS:**
1. **Change default password** immediately after login
2. **Enable 2FA** for enhanced security
3. **Create bot instances** with individual Telegram configurations
4. **Create additional users** with appropriate roles

---

## 📊 **SERVICE MONITORING**

### **Render Dashboard - Services Tab:**
Monitor all services from your Render dashboard:

#### **Web Service Metrics:**
- Response times and throughput
- Memory and CPU usage
- Request logs and errors
- Health check status

#### **Worker Service Metrics:**
- Background job processing
- Memory usage patterns
- Error rates and restarts
- Polling frequency stats

#### **Database Metrics:**
- Connection count
- Query performance
- Storage usage
- Backup status

---

## 🔧 **SCALING & PERFORMANCE**

### **Automatic Scaling:**
Each service can be scaled independently:
- **Web Service**: Handle more dashboard users
- **Worker Service**: Process more polling tasks
- **Strategy Monitor**: Analyze more strategies
- **Database**: Upgrade storage and connections

### **Performance Optimization:**
- Services run in parallel for better performance
- Database queries are optimized across services
- Background tasks don't affect dashboard responsiveness
- Real-time updates via WebSocket streaming

---

## 🌍 **ENVIRONMENT VARIABLES**

### **Required for All Services:**
```env
DATABASE_URL=postgresql://[auto-generated]
SECRET_KEY=[auto-generated]
JWT_SECRET=[auto-generated]
ALGORITHM=HS256
APP_NAME=TAR Global Strategies Dashboard
DEBUG=false
ENVIRONMENT=production
```

### **⚠️ Telegram Configuration:**
**Telegram tokens are NOT set as environment variables!**

Instead, configure Telegram **per bot instance** in the dashboard:
1. **Login to dashboard** after deployment
2. **Create/Edit Bot Instance** → Add Telegram Bot Token & Chat ID
3. **Create Strategy Monitor** → Configure Telegram notifications
4. **Each instance can have different Telegram settings**

This allows:
- **Different bots** → **Different Telegram channels**
- **Per-strategy notifications** → **Targeted alerts**
- **Flexible notification routing** → **Custom chat groups**

---

## 🧪 **TESTING DEPLOYMENT**

### **Test Each Service:**

#### **1. Web Service Test:**
```bash
curl https://tar-dashboard-web.onrender.com/api/health
# Expected: {"status": "healthy"}
```

#### **2. Database Connection Test:**
Login to dashboard and check:
- User authentication works
- Bot instances load
- API credentials management
- Real-time data updates

#### **3. Worker Service Test:**
- Create a new bot instance
- **Add Telegram Bot Token & Chat ID** to the instance
- Verify polling starts automatically
- Check for Telegram notifications in your configured channel
- Monitor activity logs

#### **4. Strategy Monitor Test:**
- View strategy monitors section
- Check performance analytics
- Verify data aggregation

---

## 🔄 **UPDATING DEPLOYMENT**

### **Code Updates:**
1. **Push to GitHub**: `git push origin master`
2. **Auto-Deploy**: All services rebuild automatically
3. **Zero Downtime**: Services restart independently
4. **Migration**: Database migrations run automatically

### **Service Configuration:**
- Update environment variables in Render dashboard
- Restart individual services as needed
- Scale services independently
- Monitor deployment logs

---

## 🚨 **TROUBLESHOOTING**

### **Service Startup Issues:**

#### **Web Service Won't Start:**
```
❌ Database migrations failed!
```
**Solution**: Check DATABASE_URL connection to PostgreSQL

#### **Worker Service Crashes:**
```
❌ Failed to connect to database
```
**Solution**: Ensure database service is running first

#### **Strategy Monitor Issues:**
```
❌ No strategy monitors found
```
**Solution**: This is normal on first deployment

### **Common URLs:**
- **Dashboard**: `https://tar-dashboard-web.onrender.com`
- **Health Check**: `https://tar-dashboard-web.onrender.com/api/health`
- **API Docs**: `https://tar-dashboard-web.onrender.com/docs`

---

## 🎉 **DEPLOYMENT COMPLETE**

Your **TAR Global Strategies Dashboard** is now running as a **multi-service architecture** with:

✅ **4 Independent Services** - Web, Worker, Strategy Monitor, Database  
✅ **Automatic Database Migrations** - PostgreSQL setup and schema updates  
✅ **Background Processing** - Independent worker services  
✅ **Real-time Monitoring** - Live dashboard updates  
✅ **Scalable Architecture** - Each service scales independently  
✅ **Production Security** - Auto-generated secrets and secure defaults  
✅ **Professional Branding** - TAR Global Strategies theme  

**🚀 Your advanced multi-service crypto monitoring platform is live!**

---

## 💰 **DEPLOYMENT COSTS & ALTERNATIVES**

### **Multi-Service Architecture (Recommended):**
- **Web Service**: $7/month (Starter plan)
- **Worker Service**: $7/month (Starter plan) 
- **Strategy Monitor**: $7/month (Starter plan)
- **PostgreSQL Database**: $7/month (Starter plan)
- **Total**: ~$28/month for full separation of concerns

### **Cost-Optimized Alternative:**
If you want to reduce costs, you can run everything in the web service:
1. Comment out the worker services in `render.yaml`
2. Use only the web service (all-in-one deployment)
3. **Cost**: $7/month (single starter service)
4. **Trade-off**: Less scalable, background tasks may affect dashboard performance

---

## 📞 **SUPPORT**

For deployment issues:
1. **Check Render Service Logs** - Each service has detailed logs
2. **Monitor Database Connections** - Ensure all services connect
3. **Test Individual Services** - Verify each component works
4. **Check Environment Variables** - Ensure all secrets are set

**Your multi-service TAR Global Strategies Dashboard is production-ready!** 