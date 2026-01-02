"""
JWT Authentication Middleware for SAVO
Validates Supabase JWT tokens and extracts user_id
"""

from fastapi import Header, HTTPException, status, Depends
import jwt
from jwt.exceptions import InvalidTokenError
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Get Supabase JWT secret from environment
# This is the JWT secret from Supabase project settings
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_JWT_SECRET:
    logger.warning("SUPABASE_JWT_SECRET not set - JWT validation will fail")


async def get_current_user(authorization: str = Header(None, alias="Authorization")) -> str:
    """
    Dependency that validates JWT token and returns user_id.
    
    Usage in routes:
        @router.get("/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}
    
    Args:
        authorization: Authorization header with format "Bearer <token>"
    
    Returns:
        user_id: UUID string from JWT 'sub' claim
    
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate JWT token
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: JWT secret not configured"
        )
    
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "require": ["exp", "sub"]
            }
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID (sub claim)",
            )
        
        logger.debug(f"Authenticated user: {user_id}")
        return user_id
        
    except InvalidTokenError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(authorization: str = Header(None, alias="Authorization")) -> Optional[str]:
    """
    Optional authentication - returns user_id if token provided, else None.
    Useful for routes that work for both authenticated and anonymous users.
    
    Usage in routes:
        @router.get("/public-or-private")
        async def flexible_route(user_id: Optional[str] = Depends(get_current_user_optional)):
            if user_id:
                return {"message": "Authenticated", "user_id": user_id}
            return {"message": "Anonymous"}
    
    Args:
        authorization: Authorization header (optional)
    
    Returns:
        user_id: UUID string if authenticated, None otherwise
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


def verify_user_owns_resource(user_id: str, resource_user_id: str) -> None:
    """
    Helper function to verify user owns a resource.
    Raises 403 if user doesn't own the resource.
    
    Usage:
        verify_user_owns_resource(current_user_id, household.user_id)
    
    Args:
        user_id: Current authenticated user ID
        resource_user_id: User ID associated with the resource
    
    Raises:
        HTTPException: 403 if user doesn't own the resource
    """
    if user_id != resource_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
