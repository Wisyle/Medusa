# Custom Domain Setup Guide - Namecheap + Render

## 🎯 Overview
Connect your Namecheap domain to your Render web service for professional branding.

## 📋 Prerequisites
- ✅ Domain purchased from Namecheap
- ✅ Render web service deployed
- ✅ Access to Namecheap control panel

## 🚀 Step 1: Configure Render Custom Domain

### 1.1 Add Custom Domain in Render
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your **tar-dashboard-web** service
3. Click **Settings** tab
4. Scroll to **Custom Domains** section
5. Click **+ Add Custom Domain**
6. Enter your domain (e.g., `yourdomain.com` or `dashboard.yourdomain.com`)
7. Click **Save**

### 1.2 Get DNS Records from Render
After adding the domain, Render will show you:
- **CNAME Record** (for subdomains like www or dashboard)
- **A Records** (for root domain)

**Example:**
```
Type: CNAME
Name: www (or dashboard)
Value: tar-dashboard-web.onrender.com

Type: A
Name: @
Value: 216.24.57.1 (example IP)
```

## 🌐 Step 2: Configure Namecheap DNS

### 2.1 Access Namecheap DNS Management
1. Login to [Namecheap](https://namecheap.com)
2. Go to **Domain List**
3. Click **Manage** next to your domain
4. Click **Advanced DNS** tab

### 2.2 Add DNS Records

**For subdomain (recommended):**
```
Type: CNAME Record
Host: dashboard (or www)
Value: tar-dashboard-web.onrender.com
TTL: Automatic
```

**For root domain:**
```
Type: A Record
Host: @
Value: [IP from Render]
TTL: Automatic

Type: CNAME Record  
Host: www
Value: yourdomain.com
TTL: Automatic
```

### 2.3 Remove Conflicting Records
- Delete any existing **A records** for @ or www
- Delete any existing **CNAME records** for the same hosts
- Keep **MX records** (for email) if you use email with this domain

## ⏱️ Step 3: Wait for Propagation

### 3.1 DNS Propagation Time
- **Typical**: 30 minutes - 2 hours  
- **Maximum**: 24-48 hours
- **Check status**: Use [DNS Checker](https://dnschecker.org)

### 3.2 Verify Setup
1. Test with: `nslookup yourdomain.com`
2. Check Render dashboard shows ✅ **Verified**
3. Visit your custom domain in browser

## 🔧 Step 4: SSL Certificate (Automatic)

### 4.1 Render Auto-SSL
- ✅ Render automatically provisions **Let's Encrypt SSL**
- ✅ Certificate renews automatically
- ✅ Redirects HTTP → HTTPS automatically

### 4.2 Verification
- Green padlock 🔒 in browser
- `https://` works without warnings
- HTTP redirects to HTTPS

## 📝 Example Configuration

### Your Setup Should Look Like:
```
Domain: yourdomain.com
Subdomain: dashboard.yourdomain.com

Namecheap DNS:
┌─────────────────────────────────────┐
│ Type: CNAME                         │
│ Host: dashboard                     │
│ Value: tar-dashboard-web.onrender.com │
│ TTL: Automatic                      │
└─────────────────────────────────────┘

Render Custom Domain:
┌─────────────────────────────────────┐
│ Domain: dashboard.yourdomain.com    │
│ Status: ✅ Verified                 │
│ SSL: ✅ Active                      │
└─────────────────────────────────────┘
```

## 🎯 Recommended Domain Strategy

### Option 1: Subdomain (Easier)
- **Domain**: `dashboard.yourdomain.com`
- **DNS**: One CNAME record
- **Benefits**: No conflicts with existing setup

### Option 2: Root Domain (Advanced)
- **Domain**: `yourdomain.com`  
- **DNS**: A records + www redirect
- **Benefits**: Shorter URL

## 🛠️ Troubleshooting

### Common Issues:

**1. Domain not verifying in Render**
- Wait 2+ hours for DNS propagation
- Check DNS records with `nslookup`
- Ensure no conflicting records

**2. SSL certificate pending**
- Wait for domain verification first
- Can take up to 24 hours
- Check for DNS conflicts

**3. 502/503 errors on custom domain**
- Verify Render service is healthy
- Check custom domain points to correct service
- Test original `.onrender.com` URL first

### Commands to Test:
```bash
# Check DNS resolution
nslookup yourdomain.com

# Check SSL certificate
curl -I https://yourdomain.com

# Test connectivity
ping yourdomain.com
```

## 📞 Need Help?

**Render Support**: [docs.render.com](https://docs.render.com/custom-domains)
**Namecheap Support**: [support.namecheap.com](https://support.namecheap.com)

## ✅ Checklist

- [ ] Added custom domain in Render
- [ ] Copied DNS records from Render  
- [ ] Added CNAME/A records in Namecheap
- [ ] Removed conflicting DNS records
- [ ] Waited for DNS propagation (30min-2h)
- [ ] Verified domain in Render dashboard
- [ ] Tested HTTPS access
- [ ] Confirmed SSL certificate active

---

🎉 **Success!** Your TAR Dashboard is now accessible via your custom domain with automatic SSL! 