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
    TEMPORARY: Validation disabled for debugging
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    
    # Extract token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    
    # TEMPORARY: Decode without verification to get user_id
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )
        
        logger.info(f"Auth bypassed for user: {user_id}")
        return user_id
        
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
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
