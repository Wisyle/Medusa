# Decter Engine Credentials Persistence Fix

## Problem Identified
The Decter engine credentials were not persisting between page reloads. Users had to re-enter their Telegram and Deriv API credentials every time they navigated away from the page and came back.

## Root Causes Found

### 1. Missing Credential Loading
The `loadCredentials()` function existed but was **never being called** when the credentials modal opened. This meant saved credentials were never loaded from the backend.

### 2. Frontend-Backend Mismatch  
The frontend was saving a single `deriv_api_key` field, but the backend expected currency-specific API tokens like:
- `xrp_api_token`
- `btc_api_token` 
- `eth_api_token`
- etc.

This mismatch meant the API keys were saved incorrectly and couldn't be retrieved properly.

## Fixes Applied

### 1. Added Credential Loading to Modal
**Fixed in**: `templates/decter_engine.html`
- Added `await loadCredentials()` calls to all three paths in `openCredentialsModalDecter()`
- Credentials are now loaded every time the modal opens

### 2. Fixed Currency-Specific API Key Handling
**Frontend Changes**:
- Updated `saveCredentials()` to save API key for the currently selected currency
- Modified `loadCredentials()` to check for the current currency's API token
- Added `updateApiKeyPlaceholder()` function to show appropriate placeholders

**Example**: If XRP is selected, the API key is saved as `xrp_api_token` instead of `deriv_api_key`

### 3. Enhanced User Experience
- Added dynamic placeholders that show "XRP API Key configured" when a key exists
- API key field updates when currency is changed
- Clear visual feedback about which currencies have keys configured

## Code Changes Summary

### New Functions Added:
```javascript
async function updateApiKeyPlaceholder(currency) {
    // Updates the API key field placeholder based on current currency
    // Shows if a key is configured for that currency
}
```

### Modified Functions:
- `openCredentialsModalDecter()` - Now calls `loadCredentials()` 
- `saveCredentials()` - Now saves currency-specific API tokens
- `loadCredentials()` - Now checks for currency-specific tokens
- `handleCurrencyChange()` - Now updates API key placeholders

### Backend Integration:
The fix leverages the existing backend structure that already supported currency-specific tokens:
- `/api/decter/telegram/config` (GET/POST) 
- `/api/decter/deriv/config` (GET/POST)

## Result
✅ **Credentials now persist correctly**
- Telegram configuration (Group ID, Topic ID, Bot Token status) loads on modal open
- Deriv configuration (App ID, API Key status for current currency) loads on modal open  
- Currency-specific API keys are saved and loaded properly
- Visual feedback shows users which currencies have keys configured

## Testing Checklist
- [x] Save Telegram credentials → Navigate away → Return → Credentials should be loaded
- [x] Save Deriv credentials for XRP → Switch to BTC → Should show no key configured
- [x] Save different API keys for different currencies → Switch between currencies → Should show appropriate status
- [x] Placeholder text should update when currency changes
- [x] All credentials should persist across browser refreshes

The credentials persistence issue is now fully resolved!
