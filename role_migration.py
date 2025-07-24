"""
Role-based Access Control Migration Script
Creates default roles and permissions for the TAR Global Strategies Dashboard
"""

from sqlalchemy.orm import Session
from database import engine, Role, Permission, RolePermission, User, UserRole
from datetime import datetime

def create_default_permissions():
    """Create default permissions for the system"""
    permissions = [
        {"name": "dashboard_read", "description": "View dashboard", "resource": "dashboard", "action": "read"},
        
        {"name": "bot_instances_read", "description": "View bot instances", "resource": "bot_instances", "action": "read"},
        {"name": "bot_instances_write", "description": "Create/edit bot instances", "resource": "bot_instances", "action": "write"},
        {"name": "bot_instances_delete", "description": "Delete bot instances", "resource": "bot_instances", "action": "delete"},
        {"name": "bot_instances_manage", "description": "Start/stop bot instances", "resource": "bot_instances", "action": "manage"},
        
        {"name": "api_library_read", "description": "View API credentials", "resource": "api_library", "action": "read"},
        {"name": "api_library_write", "description": "Create/edit API credentials", "resource": "api_library", "action": "write"},
        {"name": "api_library_delete", "description": "Delete API credentials", "resource": "api_library", "action": "delete"},
        
        {"name": "strategy_monitors_read", "description": "View strategy monitors", "resource": "strategy_monitors", "action": "read"},
        {"name": "strategy_monitors_write", "description": "Create/edit strategy monitors", "resource": "strategy_monitors", "action": "write"},
        {"name": "strategy_monitors_delete", "description": "Delete strategy monitors", "resource": "strategy_monitors", "action": "delete"},
        
        {"name": "dex_arbitrage_read", "description": "View DEX arbitrage data", "resource": "dex_arbitrage", "action": "read"},
        {"name": "dex_arbitrage_write", "description": "Create/edit DEX arbitrage instances", "resource": "dex_arbitrage", "action": "write"},
        {"name": "dex_arbitrage_manage", "description": "Start/stop DEX arbitrage", "resource": "dex_arbitrage", "action": "manage"},
        
        {"name": "validators_read", "description": "View validator nodes", "resource": "validators", "action": "read"},
        {"name": "validators_write", "description": "Create/edit validator nodes", "resource": "validators", "action": "write"},
        {"name": "validators_manage", "description": "Manage validator operations", "resource": "validators", "action": "manage"},
        
        {"name": "system_logs_read", "description": "View system logs", "resource": "system_logs", "action": "read"},
        {"name": "users_read", "description": "View users", "resource": "users", "action": "read"},
        {"name": "users_write", "description": "Create/edit users", "resource": "users", "action": "write"},
        {"name": "users_delete", "description": "Delete users", "resource": "users", "action": "delete"},
        {"name": "users_manage", "description": "Manage user roles and permissions", "resource": "users", "action": "manage"},
        
        {"name": "account_read", "description": "View own account", "resource": "account", "action": "read"},
        {"name": "account_write", "description": "Edit own account", "resource": "account", "action": "write"},
    ]
    
    return permissions

def create_default_roles():
    """Create default roles for the system"""
    roles = [
        {
            "name": "admin",
            "description": "Full system administrator with all permissions",
            "permissions": [
                "dashboard_read", "bot_instances_read", "bot_instances_write", "bot_instances_delete", "bot_instances_manage",
                "api_library_read", "api_library_write", "api_library_delete",
                "strategy_monitors_read", "strategy_monitors_write", "strategy_monitors_delete",
                "dex_arbitrage_read", "dex_arbitrage_write", "dex_arbitrage_manage",
                "validators_read", "validators_write", "validators_manage",
                "system_logs_read", "users_read", "users_write", "users_delete", "users_manage",
                "account_read", "account_write"
            ]
        },
        {
            "name": "full-access",
            "description": "Full access to trading and monitoring features with own API library",
            "permissions": [
                "dashboard_read", "bot_instances_read", "bot_instances_write", "bot_instances_delete", "bot_instances_manage",
                "api_library_read", "api_library_write", "api_library_delete",
                "strategy_monitors_read", "strategy_monitors_write", "strategy_monitors_delete",
                "dex_arbitrage_read", "dex_arbitrage_write", "dex_arbitrage_manage",
                "validators_read", "validators_write", "validators_manage",
                "system_logs_read", "account_read", "account_write"
            ]
        },
        {
            "name": "analytics-only",
            "description": "Read-only access to dashboards and reports for auditing",
            "permissions": [
                "dashboard_read", "bot_instances_read", "api_library_read",
                "strategy_monitors_read", "dex_arbitrage_read", "validators_read",
                "system_logs_read", "account_read", "account_write"
            ]
        }
    ]
    
    return roles

def run_migration():
    """Run the role migration"""
    db = Session(bind=engine)
    
    try:
        print("Starting role migration...")
        
        print("Creating permissions...")
        permissions_data = create_default_permissions()
        permission_map = {}
        
        for perm_data in permissions_data:
            existing_perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
            if not existing_perm:
                permission = Permission(**perm_data)
                db.add(permission)
                db.flush()  # Get the ID
                permission_map[perm_data["name"]] = permission.id
                print(f"  Created permission: {perm_data['name']}")
            else:
                permission_map[perm_data["name"]] = existing_perm.id
                print(f"  Permission already exists: {perm_data['name']}")
        
        print("Creating roles...")
        roles_data = create_default_roles()
        
        for role_data in roles_data:
            existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing_role:
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"]
                )
                db.add(role)
                db.flush()  # Get the ID
                
                for perm_name in role_data["permissions"]:
                    if perm_name in permission_map:
                        role_permission = RolePermission(
                            role_id=role.id,
                            permission_id=permission_map[perm_name]
                        )
                        db.add(role_permission)
                
                print(f"  Created role: {role_data['name']} with {len(role_data['permissions'])} permissions")
            else:
                print(f"  Role already exists: {role_data['name']}")
        
        print("Assigning admin role to existing superusers...")
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role:
            superusers = db.query(User).filter(User.is_superuser == True).all()
            for user in superusers:
                existing_user_role = db.query(UserRole).filter(
                    UserRole.user_id == user.id,
                    UserRole.role_id == admin_role.id
                ).first()
                
                if not existing_user_role:
                    user_role = UserRole(
                        user_id=user.id,
                        role_id=admin_role.id,
                        assigned_by=user.id  # Self-assigned for migration
                    )
                    db.add(user_role)
                    print(f"  Assigned admin role to user: {user.email}")
                else:
                    print(f"  User already has admin role: {user.email}")
        
        db.commit()
        print("Role migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
