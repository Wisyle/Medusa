#!/usr/bin/env python3
"""
API Library Routes - Manage reusable API credentials
"""

from fastapi import FastAPI, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.database import get_db, BotInstance
from models.api_library_model import ApiCredential
from app.auth import get_current_user_html, User

templates = Jinja2Templates(directory="templates")

def add_api_library_routes(app: FastAPI):
    """Add API Library routes to the FastAPI app"""
    
    @app.get("/api-library", response_class=HTMLResponse)
    async def api_library_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_html)):
        """API Library management page"""
        # Fetch API credentials for the current user
        api_credentials = db.query(ApiCredential).filter(
            ApiCredential.user_id == current_user.id
        ).order_by(ApiCredential.name).all()
        
        return templates.TemplateResponse("api_library.html", {
            "request": request,
            "current_user": current_user,
            "api_credentials": api_credentials
        })

    @app.get("/api/api-credentials")
    async def get_api_credentials(
        request: Request,
        show_all: bool = False,
        db: Session = Depends(get_db), 
        current_user: User = Depends(get_current_user_html)
    ):
        """Get API credentials (masked for security) - filtered by user unless admin requests all"""
        query = db.query(ApiCredential)
        
        if not (current_user.is_superuser and show_all):
            query = query.filter(ApiCredential.user_id == current_user.id)
        
        credentials = query.order_by(ApiCredential.name).all()
        
        # Include user info for admins viewing all credentials
        include_user_info = current_user.is_superuser and show_all
        return [credential.to_dict(include_user_info=include_user_info) for credential in credentials]
    
    @app.get("/api/api-credentials/available")
    async def get_available_api_credentials(
        request: Request,
        exchange: Optional[str] = None, 
        db: Session = Depends(get_db), 
        current_user: User = Depends(get_current_user_html)
    ):
        """Get available (not in use) API credentials for a specific exchange - filtered by user"""
        query = db.query(ApiCredential).filter(
            ApiCredential.user_id == current_user.id,
            ApiCredential.is_active == True,
            ApiCredential.is_in_use == False
        )
        
        if exchange:
            query = query.filter(ApiCredential.exchange == exchange.lower())
        
        credentials = query.order_by(ApiCredential.name).all()
        return [credential.to_dict() for credential in credentials]
    
    @app.post("/api/api-credentials")
    async def create_api_credential(
        request: Request,
        name: str = Form(...),
        exchange: str = Form(...),
        api_key: str = Form(...),
        api_secret: str = Form(...),
        api_passphrase: str = Form(""),
        description: str = Form(""),
        tags: str = Form(""),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_html)
    ):
        """Create new API credential"""
        
        # Validate input
        if not name.strip():
            raise HTTPException(status_code=400, detail="Name is required")
        
        if not exchange.strip():
            raise HTTPException(status_code=400, detail="Exchange is required")
        
        if not api_key.strip():
            raise HTTPException(status_code=400, detail="API key is required")
        
        if not api_secret.strip():
            raise HTTPException(status_code=400, detail="API secret is required")
        
        # Check if name already exists for this user
        existing = db.query(ApiCredential).filter(
            ApiCredential.user_id == current_user.id,
            ApiCredential.name == name.strip()
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"API credential with name '{name}' already exists")
        
        # Check if API key already exists
        existing_key = db.query(ApiCredential).filter(ApiCredential.api_key == api_key.strip()).first()
        if existing_key:
            raise HTTPException(status_code=400, detail="This API key is already registered")
        
        try:
            credential = ApiCredential(
                user_id=current_user.id,
                name=name.strip(),
                exchange=exchange.strip().lower(),
                api_key=api_key.strip(),
                api_secret=api_secret.strip(),
                api_passphrase=api_passphrase.strip() if api_passphrase.strip() else None,
                description=description.strip() if description.strip() else None,
                tags=tags.strip() if tags.strip() else None
            )
            
            db.add(credential)
            db.commit()
            db.refresh(credential)
            
            return {"id": credential.id, "message": "API credential created successfully"}
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create API credential: {str(e)}")
    
    @app.put("/api/api-credentials/{credential_id}")
    async def update_api_credential(
        request: Request,
        credential_id: int,
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        is_active: Optional[bool] = Form(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_html)
    ):
        """Update API credential (non-sensitive fields only)"""
        
        credential = db.query(ApiCredential).filter(ApiCredential.id == credential_id).first()
        if not credential:
            raise HTTPException(status_code=404, detail="API credential not found")
        
        try:
            if name is not None:
                # Check if new name conflicts
                if name.strip() != credential.name:
                    existing = db.query(ApiCredential).filter(
                        ApiCredential.user_id == current_user.id,
                        ApiCredential.name == name.strip(),
                        ApiCredential.id != credential_id
                    ).first()
                    if existing:
                        raise HTTPException(status_code=400, detail=f"API credential with name '{name}' already exists")
                credential.name = name.strip()
            
            if description is not None:
                credential.description = description.strip() if description.strip() else None
            
            if tags is not None:
                credential.tags = tags.strip() if tags.strip() else None
            
            if is_active is not None:
                # If deactivating, ensure it's not in use
                if not is_active and credential.is_in_use:
                    raise HTTPException(status_code=400, detail="Cannot deactivate API credential that is currently in use")
                credential.is_active = is_active
            
            credential.updated_at = datetime.utcnow()
            db.commit()
            
            return {"message": f"API credential '{credential.name}' updated successfully"}
        
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update API credential: {str(e)}")
    
    @app.delete("/api/api-credentials/{credential_id}")
    async def delete_api_credential(
        request: Request,
        credential_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_html)
    ):
        """Delete API credential"""
        
        credential = db.query(ApiCredential).filter(
            ApiCredential.id == credential_id,
            ApiCredential.user_id == current_user.id
        ).first()
        if not credential:
            raise HTTPException(status_code=404, detail="API credential not found or access denied")
        
        # Check if it's in use
        if credential.is_in_use:
            instance = db.query(BotInstance).filter(BotInstance.api_credential_id == credential_id).first()
            instance_name = instance.name if instance else "Unknown"
            raise HTTPException(status_code=400, detail=f"Cannot delete API credential that is in use by instance '{instance_name}'")
        
        try:
            db.delete(credential)
            db.commit()
            return {"message": f"API credential '{credential.name}' deleted successfully"}
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete API credential: {str(e)}")
    
    @app.post("/api/api-credentials/{credential_id}/assign/{instance_id}")
    async def assign_api_credential(
        request: Request,
        credential_id: int,
        instance_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_html)
    ):
        """Assign API credential to instance"""
        
        credential = db.query(ApiCredential).filter(
            ApiCredential.id == credential_id,
            ApiCredential.user_id == current_user.id
        ).first()
        if not credential:
            raise HTTPException(status_code=404, detail="API credential not found or access denied")
        
        instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
        if not instance:
            raise HTTPException(status_code=404, detail="Bot instance not found")
        
        # Check if credential is available
        if credential.is_in_use:
            current_instance = db.query(BotInstance).filter(BotInstance.api_credential_id == credential_id).first()
            current_name = current_instance.name if current_instance else "Unknown"
            raise HTTPException(status_code=400, detail=f"API credential is already in use by instance '{current_name}'")
        
        # Check if exchange matches
        if credential.exchange.lower() != instance.exchange.lower():
            raise HTTPException(status_code=400, detail=f"Exchange mismatch: credential is for {credential.exchange}, instance is for {instance.exchange}")
        
        try:
            # Remove any existing API credential assignment
            if instance.api_credential_id:
                old_credential = db.query(ApiCredential).filter(ApiCredential.id == instance.api_credential_id).first()
                if old_credential:
                    old_credential.is_in_use = False
                    old_credential.current_instance_id = None
            
            # Assign new credential
            credential.is_in_use = True
            credential.current_instance_id = instance_id
            credential.last_used = datetime.utcnow()
            
            instance.api_credential_id = credential_id
            
            db.commit()
            
            return {"message": f"API credential '{credential.name}' assigned to instance '{instance.name}'"}
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to assign API credential: {str(e)}")
    
    @app.post("/api/api-credentials/{credential_id}/unassign")
    async def unassign_api_credential(
        request: Request,
        credential_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_html)
    ):
        """Unassign API credential from its current instance"""
        
        credential = db.query(ApiCredential).filter(
            ApiCredential.id == credential_id,
            ApiCredential.user_id == current_user.id
        ).first()
        if not credential:
            raise HTTPException(status_code=404, detail="API credential not found or access denied")
        
        if not credential.is_in_use:
            raise HTTPException(status_code=400, detail="API credential is not currently assigned")
        
        try:
            # Find and update the instance
            instance = db.query(BotInstance).filter(BotInstance.api_credential_id == credential_id).first()
            if instance:
                # Stop instance if it's running
                if instance.is_active:
                    instance.is_active = False
                instance.api_credential_id = None
            
            # Update credential
            credential.is_in_use = False
            credential.current_instance_id = None
            
            db.commit()
            
            instance_name = instance.name if instance else "Unknown"
            return {"message": f"API credential '{credential.name}' unassigned from instance '{instance_name}'"}
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to unassign API credential: {str(e)}")
