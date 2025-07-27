from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db, SessionLocal, engine, Base
from migration_tracking_model import MigrationHistory
from migration import migrate_database
from startup_migration import run_startup_migrations
from sqlalchemy import inspect, text
import json
import os
import subprocess
import asyncio
import psutil
import shutil
from datetime import datetime
import logging
from auth import get_current_user, get_current_user_html
from database import User
from jinja2 import Template

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/migrations", response_class=HTMLResponse)
async def migrations_dashboard(request: Request, current_user: User = Depends(get_current_user_html)):
    """Display migrations dashboard"""
    # Check if user is superuser or has admin role
    if not current_user.is_superuser:
        # Check if user has admin role
        has_admin_role = any(user_role.role.name == 'admin' for user_role in current_user.roles)
        if not has_admin_role:
            raise HTTPException(status_code=403, detail="Admin access required")
    
    from main import templates
    return templates.TemplateResponse("migrations.html", {"request": request, "current_user": current_user})

@router.get("/api/migrations/status")
async def get_migration_status(current_user: User = Depends(get_current_user)):
    """Get comprehensive migration and system status"""
    # Check if user is superuser or has admin role
    if not current_user.is_superuser:
        # Check if user has admin role
        has_admin_role = any(user_role.role.name == 'admin' for user_role in current_user.roles)
        if not has_admin_role:
            raise HTTPException(status_code=403, detail="Admin access required")
    
    db = SessionLocal()
    try:
        # Get disk usage
        disk_usage = psutil.disk_usage('/')
        disk_info = {
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'percent': disk_usage.percent,
            'total_gb': round(disk_usage.total / (1024**3), 2),
            'used_gb': round(disk_usage.used / (1024**3), 2),
            'free_gb': round(disk_usage.free / (1024**3), 2)
        }
        
        # Get database size
        db_size = 0
        if os.path.exists('medusa.db'):
            db_size = os.path.getsize('medusa.db')
        elif engine.url.drivername.startswith('postgresql'):
            result = db.execute(text("SELECT pg_database_size(current_database())")).fetchone()
            if result:
                db_size = result[0]
        
        # Check tables status
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Expected tables
        expected_tables = [
            'users', 'bot_instances', 'activity_logs', 'error_logs',
            'balance_history', 'api_credentials', 'strategy_monitors',
            'dex_arbitrage_instances', 'dex_opportunities', 'validator_nodes',
            'migration_history'
        ]
        
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        # Check columns in each table
        table_issues = []
        for table in existing_tables:
            try:
                columns = inspector.get_columns(table)
                column_names = [col['name'] for col in columns]
                
                # Check for specific required columns
                if table == 'users' and 'role' not in column_names:
                    table_issues.append({'table': 'users', 'issue': 'Missing role column'})
                if table == 'api_credentials' and 'user_id' not in column_names:
                    table_issues.append({'table': 'api_credentials', 'issue': 'Missing user_id column'})
                    
            except Exception as e:
                table_issues.append({'table': table, 'issue': str(e)})
        
        # Get migration history
        try:
            migrations = db.query(MigrationHistory).order_by(MigrationHistory.applied_at.desc()).limit(10).all()
            migration_history = [{
                'id': m.id,
                'name': m.name,
                'status': m.status,
                'applied_at': m.applied_at.isoformat() if m.applied_at else None,
                'completed_at': m.completed_at.isoformat() if m.completed_at else None,
                'error_message': m.error_message,
                'tables_affected': json.loads(m.tables_affected) if m.tables_affected else [],
                'changes_made': json.loads(m.changes_made) if m.changes_made else []
            } for m in migrations]
        except:
            migration_history = []
            if 'migration_history' not in existing_tables:
                missing_tables.append('migration_history')
        
        # Check for pending migrations
        pending_migrations = []
        
        # Smart detection of required migrations
        if missing_tables:
            pending_migrations.append({
                'name': 'create_missing_tables',
                'description': f'Create {len(missing_tables)} missing tables',
                'tables': missing_tables
            })
        
        if table_issues:
            pending_migrations.append({
                'name': 'fix_table_issues',
                'description': f'Fix {len(table_issues)} table issues',
                'issues': table_issues
            })
        
        return {
            'disk_info': disk_info,
            'database_size': db_size,
            'database_size_mb': round(db_size / (1024*1024), 2),
            'tables': {
                'existing': existing_tables,
                'missing': missing_tables,
                'issues': table_issues,
                'total_expected': len(expected_tables),
                'total_existing': len(existing_tables)
            },
            'migration_history': migration_history,
            'pending_migrations': pending_migrations,
            'last_check': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting migration status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/api/migrations/run")
async def run_migrations(current_user: User = Depends(get_current_user)):
    """Run migrations and restart service"""
    # Check if user is superuser or has admin role
    if not current_user.is_superuser:
        # Check if user has admin role
        has_admin_role = any(user_role.role.name == 'admin' for user_role in current_user.roles)
        if not has_admin_role:
            raise HTTPException(status_code=403, detail="Admin access required")
    
    db = SessionLocal()
    migration_record = None
    
    try:
        # Create migration record
        migration_record = MigrationHistory(
            name=f"manual_migration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            status='running'
        )
        
        # Ensure migration_history table exists
        MigrationHistory.__table__.create(engine, checkfirst=True)
        
        db.add(migration_record)
        db.commit()
        
        logger.info("🚀 Starting manual migration...")
        
        # Gather initial state
        inspector = inspect(engine)
        initial_tables = inspector.get_table_names()
        
        changes_made = []
        tables_affected = []
        
        # Run migrations
        try:
            # First run startup migrations
            logger.info("Running startup migrations...")
            run_startup_migrations()
            changes_made.append("Ran startup migrations")
            
            # Then run regular migrations
            logger.info("Running regular migrations...")
            migrate_database()
            changes_made.append("Ran database migrations")
            
            # Check what changed
            final_tables = inspector.get_table_names()
            new_tables = [t for t in final_tables if t not in initial_tables]
            
            if new_tables:
                changes_made.append(f"Created tables: {', '.join(new_tables)}")
                tables_affected.extend(new_tables)
            
            # Update migration record
            migration_record.status = 'completed'
            migration_record.completed_at = datetime.utcnow()
            migration_record.tables_affected = json.dumps(tables_affected)
            migration_record.changes_made = json.dumps(changes_made)
            db.commit()
            
            # Restart service if on Render
            if os.getenv('RENDER'):
                logger.info("🔄 Triggering service restart on Render...")
                # Render will automatically restart when process exits
                restart_command = 'kill -HUP 1'
                subprocess.run(restart_command, shell=True)
            
            return {
                'success': True,
                'message': 'Migrations completed successfully',
                'changes': changes_made,
                'tables_affected': tables_affected,
                'restart_triggered': bool(os.getenv('RENDER'))
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if migration_record:
                migration_record.status = 'failed'
                migration_record.error_message = str(e)
                migration_record.completed_at = datetime.utcnow()
                db.commit()
            raise
            
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/api/migrations/analyze")
async def analyze_schema(current_user: User = Depends(get_current_user)):
    """Analyze database schema and suggest migrations"""
    # Check if user is superuser or has admin role
    if not current_user.is_superuser:
        # Check if user has admin role
        has_admin_role = any(user_role.role.name == 'admin' for user_role in current_user.roles)
        if not has_admin_role:
            raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        inspector = inspect(engine)
        analysis = {
            'tables': {},
            'recommendations': []
        }
        
        # Analyze each table
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            analysis['tables'][table_name] = {
                'columns': [{'name': col['name'], 'type': str(col['type'])} for col in columns],
                'indexes': indexes,
                'foreign_keys': foreign_keys
            }
            
            # Check for common issues
            column_names = [col['name'] for col in columns]
            
            # Check for missing indexes on foreign keys
            for fk in foreign_keys:
                if not any(fk['constrained_columns'][0] in idx['column_names'] for idx in indexes):
                    analysis['recommendations'].append({
                        'type': 'index',
                        'table': table_name,
                        'column': fk['constrained_columns'][0],
                        'reason': 'Foreign key without index'
                    })
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing schema: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 