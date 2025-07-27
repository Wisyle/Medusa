#!/usr/bin/env python3
"""
Debug routes for checking production database state
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, BotInstance, User
from api_library_model import ApiCredential
from auth import get_current_user
import json

router = APIRouter()

@router.get("/api/debug/instances")
async def debug_instances(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Debug endpoint to check instance ownership and API access"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        # Get all users
        users = db.query(User).all()
        users_data = [{"id": u.id, "email": u.email, "is_superuser": u.is_superuser} for u in users]
        
        # Get all API credentials
        credentials = db.query(ApiCredential).all()
        creds_data = [{"id": c.id, "user_id": c.user_id, "name": c.name, "is_active": c.is_active, "exchange": c.exchange} for c in credentials]
        
        # Get all instances with detailed info
        instances = db.query(BotInstance).all()
        instances_data = []
        
        for instance in instances:
            # Get owner info
            owner = db.query(User).filter(User.id == instance.user_id).first() if instance.user_id else None
            
            # Check API credential access
            api_access_result = "UNKNOWN"
            try:
                creds = instance.get_api_credentials()
                if creds and creds.get('api_key'):
                    api_access_result = "SUCCESS"
                else:
                    api_access_result = "FAILED - No credentials"
            except Exception as e:
                api_access_result = f"ERROR - {str(e)}"
            
            # Check API credential ownership
            api_cred_owner = None
            if instance.api_credential_id:
                api_cred = db.query(ApiCredential).filter(ApiCredential.id == instance.api_credential_id).first()
                api_cred_owner = api_cred.user_id if api_cred else "CREDENTIAL_NOT_FOUND"
            
            instance_data = {
                "id": instance.id,
                "name": instance.name,
                "user_id": instance.user_id,
                "owner_email": owner.email if owner else "NO_OWNER",
                "owner_is_super": owner.is_superuser if owner else None,
                "exchange": instance.exchange,
                "balance_enabled": instance.balance_enabled,
                "api_credential_id": instance.api_credential_id,
                "api_credential_owner": api_cred_owner,
                "has_direct_api_key": bool(instance.api_key),
                "is_active": instance.is_active,
                "api_access_result": api_access_result
            }
            instances_data.append(instance_data)
        
        return {
            "users": users_data,
            "api_credentials": creds_data,
            "instances": instances_data,
            "summary": {
                "total_users": len(users_data),
                "total_credentials": len(creds_data),
                "total_instances": len(instances_data),
                "instances_without_user_id": len([i for i in instances_data if not i["user_id"]]),
                "instances_with_api_access_issues": len([i for i in instances_data if "FAILED" in i["api_access_result"] or "ERROR" in i["api_access_result"]])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.post("/api/debug/fix-ownership")
async def fix_instance_ownership(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Fix instance ownership issues"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        changes = []
        
        # Fix instances without user_id
        instances_without_user = db.query(BotInstance).filter(BotInstance.user_id.is_(None)).all()
        if instances_without_user:
            # Assign to first non-super user if exists, otherwise to admin
            regular_user = db.query(User).filter(User.is_superuser == False).first()
            target_user = regular_user if regular_user else db.query(User).filter(User.is_superuser == True).first()
            
            if target_user:
                for instance in instances_without_user:
                    instance.user_id = target_user.id
                    changes.append(f"Assigned instance {instance.name} to user {target_user.email}")
                
                db.commit()
        
        return {
            "success": True,
            "changes": changes
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fix failed: {str(e)}")

def add_debug_routes(app):
    """Add debug routes to the FastAPI app"""
    app.include_router(router) 