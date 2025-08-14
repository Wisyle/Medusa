# TGL MEDUSA Folder Structure

This document describes the reorganized folder structure of the TGL MEDUSA project.

## Overview

The project has been reorganized for better maintainability and deployment. All imports have been updated to reflect the new structure.

## Folder Structure

```
tarc/
├── app/                        # Core application files
│   ├── __init__.py
│   ├── main.py                # FastAPI application entry point
│   ├── config.py              # Configuration settings
│   ├── database.py            # Database connection and base models
│   ├── auth.py                # Authentication logic
│   ├── config.json            # Configuration file
│   └── routes/                # API route handlers
│       ├── __init__.py
│       ├── api_library_routes.py
│       ├── decter_routes.py
│       ├── dex_arbitrage_routes.py
│       ├── migration_routes.py
│       ├── strategy_monitor_routes.py
│       ├── validator_node_routes.py
│       └── webhook_routes.py
│
├── models/                    # Database models
│   ├── __init__.py
│   ├── api_library_model.py
│   ├── dex_arbitrage_model.py
│   ├── migration_tracking_model.py
│   ├── strategy_monitor_model.py
│   └── validator_node_model.py
│
├── services/                  # Business logic and services
│   ├── __init__.py
│   ├── notification_service.py
│   ├── polling.py
│   ├── rest_client.py
│   ├── ws_client.py
│   ├── worker.py
│   ├── worker_standalone.py
│   ├── decter_controller.py
│   ├── dex_arbitrage_monitor.py
│   ├── strategy_monitor.py
│   ├── strategy_monitor_worker.py
│   └── strategic_monitors.py
│
├── migrations/                # Database migration scripts
│   ├── __init__.py
│   ├── migration.py
│   ├── migrate_api_library.py
│   ├── migrate_enhanced.py
│   ├── role_migration.py
│   ├── run_migrations.py
│   ├── startup_migration.py
│   └── enable_balance_migration.sql
│
├── utils/                     # Utility scripts
│   ├── __init__.py
│   ├── init_db.py
│   ├── init_strategy_monitor.py
│   ├── create_admin_user.py
│   ├── startup_optimization.py
│   ├── setup_decter_integration.py
│   ├── update_polling_api.py
│   ├── update_trading_pair.py
│   ├── validate_deployment.py
│   ├── validate_render_yaml.py
│   ├── pre_deployment_validation.py
│   ├── post_deployment_validation.py
│   ├── render_readiness_check.py
│   ├── render_startup_fix.py
│   ├── deploy_with_enhancements.py
│   ├── emergency_rollback.py
│   ├── fix_balance_enabled.py
│   ├── fix_decter_startup.py
│   ├── fix_runtime_issues.py
│   ├── fix_strategy_monitor.py
│   ├── fix_trading_pair.py
│   └── force_decter_redeploy.py
│
├── docs/                      # Documentation
│   ├── __init__.py
│   ├── API_LIBRARY_IMPLEMENTATION.md
│   ├── CLOUDFRONT_BYPASS_SOLUTION.md
│   ├── CUSTOM_DOMAIN_SETUP.md
│   ├── DASHBOARD_ACCESS.md
│   ├── DASHBOARD_IMPLEMENTATION_COMPLETE.md
│   ├── DECTER_INTEGRATION.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DEPLOYMENT.md
│   ├── READY_TO_DEPLOY.md
│   ├── RENDER_DEPLOYMENT_GUIDE.md
│   └── RENDER_SETUP.md
│
├── Decter/                    # Decter engine (unchanged)
│   └── [Decter files...]
│
├── static/                    # Static files (unchanged)
│   └── [CSS, JS, images...]
│
├── templates/                 # HTML templates (unchanged)
│   └── [HTML files...]
│
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
├── render.yaml               # Render deployment configuration
├── start.sh                  # Application startup script
├── start_strategy_monitor.sh # Strategy monitor startup script
├── medusa.db                # SQLite database (development)
├── README.md                 # Project documentation
└── FOLDER_STRUCTURE.md       # This file
```

## Import Changes

All imports have been updated to use the new structure:

### From Root Imports
- `from database import ...` → `from app.database import ...`
- `from config import ...` → `from app.config import ...`
- `from auth import ...` → `from app.auth import ...`

### Model Imports
- `from api_library_model import ...` → `from models.api_library_model import ...`
- `from dex_arbitrage_model import ...` → `from models.dex_arbitrage_model import ...`
- etc.

### Service Imports
- `from polling import ...` → `from services.polling import ...`
- `from notification_service import ...` → `from services.notification_service import ...`
- etc.

### Route Imports
- `from api_library_routes import ...` → `from app.routes.api_library_routes import ...`
- etc.

### Migration Imports
- `from migration import ...` → `from migrations.migration import ...`
- etc.

## Python Path Configuration

For proper module resolution, the following configurations have been added:

1. **Dockerfile**: `ENV PYTHONPATH=/app`
2. **render.yaml**: Added `export PYTHONPATH=/opt/render/project/src` to all service start commands
3. **Migration scripts**: Added `sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` 

## Deployment Notes

1. The main application entry point is now `app.main:app` instead of `main:app`
2. All worker scripts are in the `services/` folder
3. Migration scripts are in the `migrations/` folder
4. Utility scripts are in the `utils/` folder

## Running the Application

### Development
```bash
export PYTHONPATH=.
uvicorn app.main:app --reload
```

### Production (Render)
The application will automatically set the correct PYTHONPATH and run with the updated structure.

## Removed Files

The following test and debug files have been removed:
- All `test_*.py` files
- All `debug_*.py` files
- All `check_*.py` files
- `add_debug_logging.py`
- `Hi.py`
- `tatus`
- `help`
- `migration_revert.txt`
- `templates_backup/` folder
- Various lighthouse files from root
