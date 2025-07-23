# 🚀 Deployment Checklist for TGL MEDUSA API Library

## Pre-Deployment Validation

### 1. Run Validation Script
```bash
python pre_deployment_validation.py
```
**✅ MUST PASS** - Do not deploy if this fails!

### 2. Test Local Migration
```bash
# Backup your local database first
python -c "from migration import migrate_database; migrate_database()"
```

### 3. Verify New Features Locally
- [ ] Visit `/api-library` page
- [ ] Create a test API credential
- [ ] Create a new bot instance using API Library
- [ ] Verify strategy monitor timing improvements

## Deployment Process

### 1. Commit Changes
```bash
git add .
git commit -m "feat: Add API Library system and fix strategy monitor timing

- Add comprehensive API Library with web interface
- Implement conflict prevention for API credentials
- Fix strategy monitor timing accuracy (5-min intervals)
- Add database migration for seamless upgrade
- Maintain backward compatibility with existing instances"
```

### 2. Push to Repository
```bash
git push origin main
```

### 3. Deploy to Render
- Render will automatically detect the push and start deployment
- Monitor deployment logs for any issues
- **Migration will run automatically** via the startup event in main.py

### 4. Post-Deployment Verification

#### Immediate Checks (First 5 minutes)
- [ ] Web service starts successfully
- [ ] Worker services start successfully  
- [ ] Database migration completes without errors
- [ ] All existing bot instances remain functional

#### Functional Checks (First 15 minutes)
- [ ] Access web interface at your Render URL
- [ ] Login works correctly
- [ ] Dashboard shows existing instances
- [ ] Visit `/api-library` - new page loads
- [ ] Existing bot instances still polling correctly

#### Advanced Checks (First 30 minutes)
- [ ] Create new API credential in library
- [ ] Create new bot instance using API library
- [ ] Verify conflict prevention (try using same API twice)
- [ ] Check strategy monitor timing accuracy

## Rollback Plan

If something goes wrong:

### 1. Immediate Rollback
```bash
# Revert to previous commit
git revert HEAD
git push origin main
```

### 2. Database Rollback (if needed)
The migration is additive-only and backward compatible:
- New `api_credentials` table is independent
- New `api_credential_id` column is nullable
- Existing API fields remain functional
- **No data loss risk**

## Key Safety Features

### ✅ Backward Compatibility
- Existing bot instances continue working unchanged
- Direct API credentials still supported
- No breaking changes to existing functionality

### ✅ Gradual Migration
- Users can migrate to API Library at their own pace
- Both old and new systems work simultaneously
- No forced migration required

### ✅ Safe Database Changes
- All new columns are nullable
- No existing data is modified
- Migration can be run multiple times safely

## Monitoring After Deployment

### Check These Logs
1. **Web Service Logs**: Look for "Database migration completed"
2. **Worker Logs**: Ensure polling continues normally
3. **Strategy Monitor Logs**: Verify timing improvements

### Watch These Metrics
- Existing bot instance polling intervals
- Strategy monitor report frequencies
- Web interface responsiveness
- Database connection stability

## Emergency Contacts
- Monitor Render dashboard for service health
- Check database connections in Render dashboard
- Review application logs for any migration errors

---

## Notes
- **Migration is automatic** - no manual database changes needed
- **Zero downtime** - existing services continue during migration
- **Data safety** - all changes are additive, no data loss risk
- **Testing ready** - comprehensive test suite validates all functionality
