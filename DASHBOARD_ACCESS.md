# TGL MEDUSA - Dashboard Access Guide

## 🌐 **Dashboard URL Access**

### **After Render Deployment:**
Your dashboard will be accessible at your Render app URL:

```
https://your-app-name.onrender.com
```

**Example URLs:**
- `https://tgl-medusa-loggers-web.onrender.com`
- `https://my-crypto-bot-monitor.onrender.com`

### **Finding Your Exact URL:**

#### **Method 1: Render Dashboard**
1. Login to [render.com](https://render.com)
2. Go to your **tgl-medusa-loggers-web** service
3. Copy the URL from the service overview page

#### **Method 2: Render Logs**
1. Check your deployment logs
2. Look for: `Your service is live at https://...`

#### **Method 3: Custom Domain** (Optional)
If you set up a custom domain:
- `https://yourdomain.com`
- `https://monitor.yourdomain.com`

---

## 🔐 **Dashboard Access Flow**

### **1. First Time Setup:**
```
https://your-app.onrender.com/register
```
- Register your admin account
- Set up Google Authenticator 2FA
- Scan QR code with authenticator app

### **2. Regular Login:**
```
https://your-app.onrender.com/login
```
- Enter email and password
- Enter 6-digit 2FA code from Google Authenticator

### **3. Main Dashboard:**
```
https://your-app.onrender.com/dashboard
```
- View all bot instances
- Monitor performance metrics
- Check recent activities

---

## 📱 **Dashboard Features**

### **Main Sections:**
- **Dashboard** (`/dashboard`) - Overview and metrics
- **Bot Instances** (`/instances`) - Manage trading bots
- **Create New Bot** (`/instances/new`) - Add bot instances
- **Instance Details** (`/instances/{id}`) - Individual bot management

### **API Endpoints:**
- **Health Check** (`/api/health`) - Service status
- **Bot Status** (`/api/status`) - All bots status
- **PnL Data** (`/api/pnl`) - Profit/Loss information

---

## 🚨 **Troubleshooting Access Issues**

### **Can't Access Dashboard:**
1. **Check service status** in Render dashboard
2. **Verify deployment** completed successfully
3. **Check logs** for startup errors
4. **Wait 2-3 minutes** after deployment

### **Login Issues:**
1. **Clear browser cache** and cookies
2. **Try incognito/private** browsing mode
3. **Check 2FA time sync** on your device
4. **Reset password** if needed

### **404 Errors:**
1. **Verify correct URL** format
2. **Check service is running** in Render
3. **Review deployment logs** for errors

---

## 📞 **Quick Access Checklist**

✅ **Deployment completed** without errors  
✅ **Service shows as "Live"** in Render dashboard  
✅ **Health check passes**: `https://your-app.onrender.com/api/health`  
✅ **Registration page loads**: `https://your-app.onrender.com/register`  
✅ **Admin account created** and 2FA setup completed  
✅ **Dashboard accessible**: `https://your-app.onrender.com/dashboard`  

**Ready to monitor your crypto bots! 🚀**
