from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal, engine, Base
from models.migration_tracking_model import MigrationHistory
from migrations.migration import migrate_database
from migrations.startup_migration import run_startup_migrations
from sqlalchemy import inspect, text
import json
import os
import subprocess
import asyncio
import psutil
import shutil
from datetime import datetime
import logging
from app.auth import get_current_user, get_current_user_html
from app.database import User
from jinja2 import Template
# Import models for cleanup
from app.database import ActivityLog, ErrorLog, BalanceHistory, BotInstance

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/migrations", response_class=HTMLResponse)
async def migrations_dashboard(request: Request, current_user: User = Depends(get_current_user_html)):
    """Display migrations dashboard"""
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    from main import templates
    return templates.TemplateResponse("migrations.html", {"request": request, "current_user": current_user})

@router.get("/api/migrations/status")
async def get_migration_status(current_user: User = Depends(get_current_user)):
    """Get comprehensive migration and system status"""
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
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
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
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
            # Import all models to ensure they're registered
            from database import User, Role, Permission, UserRole, RolePermission
            from dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
            from validator_node_model import ValidatorNode
            from strategy_monitor_model import StrategyMonitor
            
            logger.info("Creating all tables...")
            # Create all tables
            Base.metadata.create_all(bind=engine)
            changes_made.append("Created/updated all database tables")
            
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
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        inspector = inspect(engine)
        analysis = {
            'tables': {},
            'recommendations': []
        }
        
        # Analyze each table
        for table_name in inspector.get_table_names():
            try:
                columns = inspector.get_columns(table_name)
                indexes = inspector.get_indexes(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                # Convert column types to string representation
                column_info = []
                for col in columns:
                    col_type = str(col.get('type', 'Unknown'))
                    column_info.append({
                        'name': col['name'],
                        'type': col_type,
                        'nullable': col.get('nullable', True),
                        'default': str(col.get('default', '')) if col.get('default') else None
                    })
                
                analysis['tables'][table_name] = {
                    'columns': column_info,
                    'indexes': indexes,
                    'foreign_keys': foreign_keys
                }
                
                # Check for missing indexes on foreign keys
                for fk in foreign_keys:
                    if fk.get('constrained_columns'):
                        for col in fk['constrained_columns']:
                            # Check if any index contains this column
                            has_index = False
                            for idx in indexes:
                                if col in idx.get('column_names', []):
                                    has_index = True
                                    break
                            
                            if not has_index:
                                analysis['recommendations'].append({
                                    'type': 'index',
                                    'table': table_name,
                                    'column': col,
                                    'reason': f'Foreign key column {col} without index'
                                })
                
            except Exception as e:
                logger.error(f"Error analyzing table {table_name}: {e}")
                analysis['tables'][table_name] = {
                    'error': str(e),
                    'columns': [],
                    'indexes': [],
                    'foreign_keys': []
                }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing schema: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.post("/api/migrations/cleanup")
async def cleanup_database(current_user: User = Depends(get_current_user)):
    """Clean up unused data and optimize database"""
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    db = SessionLocal()
    cleanup_stats = {
        'test_users_removed': 0,
        'test_bots_removed': 0,
        'old_logs_removed': 0,
        'old_errors_removed': 0,
        'old_balance_removed': 0,
        'failed_migrations_removed': 0,
        'database_optimized': False,
        'errors': []
    }
    
    try:
        logger.info("🧹 Starting database cleanup...")
        
        # Remove test users
        test_emails = ['admin@test.com', 'test@test.com', 'demo@demo.com']
        test_users = db.query(User).filter(User.email.in_(test_emails)).all()
        
        if test_users:
            for user in test_users:
                logger.info(f"Removing test user: {user.email}")
                db.delete(user)
                cleanup_stats['test_users_removed'] += 1
            db.commit()
        
        # Remove test bot instances
        test_bots = db.query(BotInstance).filter(
            BotInstance.name.in_(['Test Bot', 'Demo Bot', 'Example Bot'])
        ).all()
        
        if test_bots:
            for bot in test_bots:
                logger.info(f"Removing test bot: {bot.name}")
                db.delete(bot)
                cleanup_stats['test_bots_removed'] += 1
            db.commit()
        
        # Clean up old logs (older than 30 days)
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        # Activity logs
        old_activity_logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp < cutoff_date
        ).count()
        
        if old_activity_logs > 0:
            db.query(ActivityLog).filter(
                ActivityLog.timestamp < cutoff_date
            ).delete()
            cleanup_stats['old_logs_removed'] = old_activity_logs
            db.commit()
        
        # Error logs
        old_error_logs = db.query(ErrorLog).filter(
            ErrorLog.timestamp < cutoff_date
        ).count()
        
        if old_error_logs > 0:
            db.query(ErrorLog).filter(
                ErrorLog.timestamp < cutoff_date
            ).delete()
            cleanup_stats['old_errors_removed'] = old_error_logs
            db.commit()
        
        # Balance history (older than 90 days)
        balance_cutoff = datetime.utcnow() - timedelta(days=90)
        old_balance_history = db.query(BalanceHistory).filter(
            BalanceHistory.timestamp < balance_cutoff
        ).count()
        
        if old_balance_history > 0:
            db.query(BalanceHistory).filter(
                BalanceHistory.timestamp < balance_cutoff
            ).delete()
            cleanup_stats['old_balance_removed'] = old_balance_history
            db.commit()
        
        # Clean up failed migrations
        failed_migrations = db.query(MigrationHistory).filter(
            MigrationHistory.status == 'failed'
        ).all()
        
        if failed_migrations:
            for migration in failed_migrations:
                db.delete(migration)
                cleanup_stats['failed_migrations_removed'] += 1
            db.commit()
        
        # Vacuum database to reclaim space
        try:
            is_postgresql = str(engine.url).startswith('postgresql')
            
            if is_postgresql:
                # For PostgreSQL, use raw connection
                conn = engine.raw_connection()
                conn.set_isolation_level(0)  # AUTOCOMMIT
                cursor = conn.cursor()
                cursor.execute("VACUUM ANALYZE")
                cursor.close()
                conn.close()
                cleanup_stats['database_optimized'] = True
            else:
                # SQLite vacuum
                db.execute(text("VACUUM"))
                db.commit()
                cleanup_stats['database_optimized'] = True
                
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")
            cleanup_stats['errors'].append(f"Vacuum error: {str(e)}")
        
        logger.info("✅ Database cleanup completed")
        
        return {
            'success': True,
            'message': 'Database cleanup completed successfully',
            'stats': cleanup_stats
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/api/migrations/storage-analysis")
async def analyze_storage(current_user: User = Depends(get_current_user)):
    """Analyze database storage usage"""
    # Only allow superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    db = SessionLocal()
    try:
        is_postgresql = str(engine.url).startswith('postgresql')
        storage_info = {
            'tables': [],
            'total_size': 0,
            'database_type': 'PostgreSQL' if is_postgresql else 'SQLite'
        }
        
        if is_postgresql:
            # PostgreSQL table sizes
            result = db.execute(text("""
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """))
            
            for row in result:
                storage_info['tables'].append({
                    'name': row.tablename,
                    'size': row.size,
                    'size_bytes': row.size_bytes
                })
                storage_info['total_size'] += row.size_bytes
                
            # Get total database size
            db_size_result = db.execute(text("SELECT pg_database_size(current_database())")).fetchone()
            if db_size_result:
                storage_info['total_database_size'] = db_size_result[0]
                storage_info['total_database_size_pretty'] = f"{db_size_result[0] / (1024**2):.2f} MB"
        else:
            # SQLite - just get file size
            if os.path.exists('medusa.db'):
                size = os.path.getsize('medusa.db')
                storage_info['total_size'] = size
                storage_info['total_database_size'] = size
                storage_info['total_database_size_pretty'] = f"{size / (1024**2):.2f} MB"
                
        return storage_info
        
    except Exception as e:
        logger.error(f"Error analyzing storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close() 

@router.post("/api/migrations/enable-balance-tracking")
async def enable_balance_tracking_endpoint(current_user: dict = Depends(get_current_user)):
    """Enable balance tracking for all bot instances"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    db = SessionLocal()
    try:
        # Get all instances where balance_enabled is False
        instances = db.query(BotInstance).filter(BotInstance.balance_enabled == False).all()
        
        if not instances:
            return {
                'success': True,
                'message': 'All instances already have balance tracking enabled',
                'updated_count': 0
            }
        
        # Enable balance tracking for all instances
        updated_instances = []
        for instance in instances:
            instance.balance_enabled = True
            updated_instances.append(instance.name)
        
        db.commit()
        
        return {
            'success': True,
            'message': f'Successfully enabled balance tracking for {len(instances)} instances',
            'updated_count': len(instances),
            'updated_instances': updated_instances
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to enable balance tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close() 