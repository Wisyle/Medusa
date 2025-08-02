import secrets
from datetime import datetime, timedelta
from typing import Optional, Union
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import pyotp
import qrcode
from io import BytesIO
import base64
from database import get_db, User
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer()

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None
    private_key: Optional[str] = None  # Admin private key for enhanced security
    passphrase: Optional[str] = None  # Admin passphrase for enhanced security

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    totp_enabled: bool
    has_private_key: bool = False
    has_passphrase: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SecuritySetup(BaseModel):
    setup_type: str  # "private_key", "passphrase", "totp", or "complete"
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    enable_totp: Optional[bool] = False

class AuthMethod(BaseModel):
    method: str  # "email_password", "email_password_2fa", "private_key_passphrase", "all"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # 7 days for refresh tokens
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "access":
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    return token_data

def verify_refresh_token(refresh_token: str):
    """Verify JWT refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )
    try:
        payload = jwt.decode(refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exception
        return TokenData(email=email)
    except JWTError:
        raise credentials_exception

def get_current_user(token_data: TokenData = Depends(verify_token), db: Session = Depends(get_db)):
    """Get current authenticated user."""
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def authenticate_user(db: Session, email: str, password: str, totp_code: Optional[str] = None, 
                     private_key: Optional[str] = None, passphrase: Optional[str] = None):
    """Authenticate user with flexible security modes."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    
    # For superusers, check if additional security is configured
    if user.is_superuser:
        # Check if user has any additional security configured
        has_private_key = user.private_key_hash is not None and user.private_key_hash.strip() != ""
        has_passphrase = user.passphrase_hash is not None and user.passphrase_hash.strip() != ""
        has_totp = user.totp_secret is not None and user.totp_enabled
        
        # If no additional security is configured, allow first-time login with just email/password
        if not has_private_key and not has_passphrase and not has_totp:
            # First time login - mark user as needing security setup
            user.needs_security_setup = True
            return user
        
        # If additional security is configured, enforce it
        security_checks_passed = True
        
        # Private key authentication
        if has_private_key:
            if not private_key:
                return "private_key_required"
            if not verify_password(private_key, user.private_key_hash):
                security_checks_passed = False
        
        # Passphrase authentication
        if has_passphrase:
            if not passphrase:
                return "passphrase_required"
            if not verify_password(passphrase, user.passphrase_hash):
                security_checks_passed = False
        
        # TOTP authentication
        if has_totp:
            if not totp_code:
                return "totp_required"
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(totp_code):
                security_checks_passed = False
        
        if not security_checks_passed:
            return False
    
    # For regular users, only check TOTP if enabled
    elif user.totp_secret and user.totp_enabled:
        if not totp_code:
            return "totp_required"
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code):
            return False
    
    return user

def generate_totp_secret():
    """Generate a new TOTP secret."""
    return pyotp.random_base32()

def generate_totp_qr_code(user_email: str, secret: str) -> str:
    """Generate QR code for TOTP setup."""
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email,
        issuer_name=settings.app_name
    )
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def verify_token_from_cookie_or_header(request: Request):
    """Verify JWT token from cookie or Authorization header for HTML routes."""
    token = None
    
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "access":
            return None
        return TokenData(email=email)
    except JWTError:
        return None

def get_current_user_html(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user for HTML routes - redirects to login if not authenticated."""
    token_data = verify_token_from_cookie_or_header(request)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Redirect to login",
            headers={"Location": "/login"}
        )
    
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Redirect to login",
            headers={"Location": "/login"}
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Redirect to login", 
            headers={"Location": "/login"}
        )
    
    return user

def create_user(db: Session, user_create: UserCreate):
    """Create a new user."""
    if db.query(User).filter(User.email == user_create.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user_create.password)
    db_user = User(
        email=user_create.email,
        hashed_password=hashed_password,
        full_name=user_create.full_name,
        is_active=True,
        is_superuser=False,
        totp_enabled=False,
        needs_security_setup=True  # New users need to complete security setup
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def setup_user_security(db: Session, user: User, security_setup: SecuritySetup):
    """Set up additional security for a user after first login"""
    try:
        if security_setup.private_key:
            user.private_key_hash = get_password_hash(security_setup.private_key)
        
        if security_setup.passphrase:
            user.passphrase_hash = get_password_hash(security_setup.passphrase)
        
        if security_setup.enable_totp and not user.totp_secret:
            user.totp_secret = generate_totp_secret()
            user.totp_enabled = True
        
        # Mark security setup as complete
        user.needs_security_setup = False
        
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise e

def get_user_auth_methods(user: User) -> list:
    """Get available authentication methods for a user"""
    methods = []
    
    has_private_key = user.private_key_hash is not None and user.private_key_hash.strip() != ""
    has_passphrase = user.passphrase_hash is not None and user.passphrase_hash.strip() != ""
    has_totp = user.totp_secret is not None and user.totp_enabled
    
    # Basic email/password (always available)
    methods.append({
        "method": "email_password",
        "name": "Email & Password",
        "description": "Basic authentication with email and password"
    })
    
    # Email/password + 2FA
    if has_totp:
        methods.append({
            "method": "email_password_2fa", 
            "name": "Email, Password & 2FA",
            "description": "Email, password + Google Authenticator"
        })
    
    # Private key + passphrase
    if has_private_key and has_passphrase:
        methods.append({
            "method": "private_key_passphrase",
            "name": "Private Key & Passphrase", 
            "description": "Private key with passphrase authentication"
        })
    
    # All methods combined
    if has_private_key and has_passphrase and has_totp:
        methods.append({
            "method": "all",
            "name": "Maximum Security",
            "description": "Email, password, private key, passphrase & 2FA"
        })
    
    return methods
