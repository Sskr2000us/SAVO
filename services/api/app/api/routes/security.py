"""
Session Security API Routes
Endpoints for device management, session tracking, and security monitoring
"""

from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.middleware.auth import get_current_user
from app.services.session_security import get_session_security_service, SessionSecurityService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Session Security"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LoginTrackingRequest(BaseModel):
    """Request model for tracking login"""
    session_token: str  # JWT access token


class RevokeSessionRequest(BaseModel):
    """Request model for revoking a session"""
    session_id: str


class TrustDeviceRequest(BaseModel):
    """Request model for trusting a device"""
    device_fingerprint: str
    device_name: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/track-login")
async def track_login(
    request: Request,
    tracking_data: LoginTrackingRequest,
    user_id: str = Depends(get_current_user),
    security_service: SessionSecurityService = Depends(get_session_security_service)
):
    """
    Track user login with device fingerprinting and location.
    Called after successful Supabase authentication.
    
    **BLOCKS LOGIN** if device limit exceeded (2 devices).
    
    **Returns:**
    - session_id: UUID of created session
    - device_recognized: bool indicating if device is trusted
    - location: City name from IP geolocation
    - active_devices: Current count of active sessions
    
    **Raises:**
    - 403: Device limit exceeded (max 2 devices)
    """
    try:
        result = await security_service.track_login(
            user_id=user_id,
            session_token=tracking_data.session_token,
            request=request
        )
        
        return result
        
    except HTTPException:
        raise  # Re-raise 403 device limit errors
    except Exception as e:
        logger.error(f"Error tracking login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track login session"
        )


@router.get("/sessions")
async def get_active_sessions(
    user_id: str = Depends(get_current_user),
    security_service: SessionSecurityService = Depends(get_session_security_service)
) -> Dict[str, Any]:
    """
    Get all active sessions for the authenticated user.
    
    **Returns:**
    - sessions: List of active sessions with device and location info
    - total_count: Number of active sessions
    - max_devices: Maximum allowed devices
    - can_add_device: Whether user can add another device
    """
    try:
        sessions = await security_service.get_active_sessions(user_id)
        
        # Get max devices for user
        from app.core.database import get_db_client
        supabase = get_db_client()
        user_result = supabase.table('users').select('max_devices').eq('id', user_id).execute()
        max_devices = user_result.data[0].get('max_devices', 2) if user_result.data else 2
        
        return {
            'success': True,
            'sessions': sessions,
            'total_count': len(sessions),
            'max_devices': max_devices,
            'can_add_device': len(sessions) < max_devices
        }
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active sessions"
        )


@router.post("/sessions/revoke")
async def revoke_session(
    revoke_data: RevokeSessionRequest,
    user_id: str = Depends(get_current_user),
    security_service: SessionSecurityService = Depends(get_session_security_service)
):
    """
    Revoke a specific session (sign out specific device).
    
    **Note:** The actual Supabase JWT remains valid until expiry.
    This marks the session as inactive in our tracking system.
    For full enforcement, implement token blacklist or use Supabase Admin API.
    """
    try:
        success = await security_service.revoke_session(user_id, revoke_data.session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or already revoked"
            )
        
        return {
            'success': True,
            'message': 'Session revoked successfully',
            'session_id': revoke_data.session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    request: Request,
    current_token: LoginTrackingRequest,
    user_id: str = Depends(get_current_user),
    security_service: SessionSecurityService = Depends(get_session_security_service)
):
    """
    Revoke all sessions EXCEPT the current one.
    Equivalent to "Sign out all other devices".
    
    **Returns:**
    - revoked_count: Number of sessions revoked
    """
    try:
        import hashlib
        token_hash = hashlib.sha256(current_token.session_token.encode()).hexdigest()[:32]
        
        revoked_count = await security_service.revoke_other_sessions(user_id, token_hash)
        
        return {
            'success': True,
            'message': f'Signed out {revoked_count} other device(s)',
            'revoked_count': revoked_count
        }
        
    except Exception as e:
        logger.error(f"Error revoking other sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke other sessions"
        )


@router.get("/events")
async def get_security_events(
    limit: int = 50,
    severity: Optional[str] = None,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get security events for the authenticated user.
    
    **Query Parameters:**
    - limit: Maximum number of events to return (default: 50, max: 200)
    - severity: Filter by severity ('info', 'warning', 'critical')
    
    **Returns:**
    - events: List of security events
    - unresolved_count: Number of events requiring user action
    """
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        # Validate limit
        limit = min(limit, 200)
        
        # Build query
        query = supabase.table('security_events').select('*').eq('user_id', user_id)
        
        if severity:
            query = query.eq('severity', severity)
        
        query = query.order('created_at', desc=True).limit(limit)
        
        result = query.execute()
        
        # Count unresolved events
        unresolved_result = supabase.table('security_events').select('id', count='exact').eq(
            'user_id', user_id
        ).eq('requires_user_action', True).is_('resolved_at', 'null').execute()
        
        unresolved_count = unresolved_result.count if hasattr(unresolved_result, 'count') else 0
        
        return {
            'success': True,
            'events': result.data,
            'total_count': len(result.data),
            'unresolved_count': unresolved_count
        }
        
    except Exception as e:
        logger.error(f"Error getting security events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security events"
        )


@router.post("/events/{event_id}/resolve")
async def resolve_security_event(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark a security event as resolved"""
    try:
        from datetime import datetime
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        result = supabase.table('security_events').update({
            'resolved_at': datetime.utcnow().isoformat()
        }).eq('id', event_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Security event not found"
            )
        
        return {
            'success': True,
            'message': 'Security event resolved'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving security event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve security event"
        )


@router.get("/trusted-devices")
async def get_trusted_devices(
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get list of trusted devices for user"""
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        result = supabase.table('trusted_devices').select('*').eq(
            'user_id', user_id
        ).eq('is_active', True).order('last_used_at', desc=True).execute()
        
        return {
            'success': True,
            'devices': result.data,
            'total_count': len(result.data)
        }
        
    except Exception as e:
        logger.error(f"Error getting trusted devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trusted devices"
        )


@router.post("/trusted-devices")
async def trust_device(
    trust_data: TrustDeviceRequest,
    user_id: str = Depends(get_current_user)
):
    """Add a device to trusted devices list"""
    try:
        from datetime import datetime
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        # Get device info from active sessions
        session_result = supabase.table('user_sessions').select('*').eq(
            'user_id', user_id
        ).eq('device_fingerprint', trust_data.device_fingerprint).eq(
            'is_active', True
        ).limit(1).execute()
        
        if not session_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found in active sessions"
            )
        
        session = session_result.data[0]
        
        # Add to trusted devices
        device_data = {
            'user_id': user_id,
            'device_fingerprint': trust_data.device_fingerprint,
            'device_name': trust_data.device_name or f"{session.get('device_os')} Device",
            'device_type': session.get('device_type'),
            'device_os': session.get('device_os'),
            'trusted_at': datetime.utcnow().isoformat(),
            'last_used_at': datetime.utcnow().isoformat(),
            'is_active': True
        }
        
        result = supabase.table('trusted_devices').upsert(
            device_data,
            on_conflict='user_id,device_fingerprint'
        ).execute()
        
        # Update session to mark as trusted
        supabase.table('user_sessions').update({
            'is_trusted': True
        }).eq('user_id', user_id).eq('device_fingerprint', trust_data.device_fingerprint).execute()
        
        return {
            'success': True,
            'message': 'Device added to trusted list',
            'device': result.data[0] if result.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error trusting device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trust device"
        )


@router.delete("/trusted-devices/{device_id}")
async def untrust_device(
    device_id: str,
    user_id: str = Depends(get_current_user)
):
    """Remove a device from trusted devices list"""
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        result = supabase.table('trusted_devices').update({
            'is_active': False
        }).eq('id', device_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trusted device not found"
            )
        
        return {
            'success': True,
            'message': 'Device removed from trusted list'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error untrusting device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to untrust device"
        )


@router.get("/dashboard")
async def get_security_dashboard(
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get security dashboard summary for user.
    
    **Returns:**
    - active_sessions: Count and list of active sessions
    - recent_events: Last 10 security events
    - unresolved_alerts: Count of events requiring action
    - trusted_devices: Count of trusted devices
    - security_score: Overall security score (0-100)
    """
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        # Get active sessions count
        sessions_result = supabase.rpc(
            'get_active_session_count',
            {'p_user_id': user_id}
        ).execute()
        active_sessions = sessions_result.data if sessions_result.data else 0
        
        # Get recent security events
        events_result = supabase.table('security_events').select('*').eq(
            'user_id', user_id
        ).order('created_at', desc=True).limit(10).execute()
        
        # Get unresolved alerts
        unresolved_result = supabase.table('security_events').select('id', count='exact').eq(
            'user_id', user_id
        ).eq('requires_user_action', True).is_('resolved_at', 'null').execute()
        unresolved_count = unresolved_result.count if hasattr(unresolved_result, 'count') else 0
        
        # Get trusted devices count
        trusted_result = supabase.table('trusted_devices').select('id', count='exact').eq(
            'user_id', user_id
        ).eq('is_active', True).execute()
        trusted_count = trusted_result.count if hasattr(trusted_result, 'count') else 0
        
        # Get user's max devices
        user_result = supabase.table('users').select('max_devices').eq('id', user_id).execute()
        max_devices = user_result.data[0].get('max_devices', 2) if user_result.data else 2
        
        # Calculate security score (simple heuristic)
        security_score = 100
        if unresolved_count > 0:
            security_score -= min(unresolved_count * 10, 30)
        if active_sessions > max_devices:
            security_score -= 40
        if trusted_count == 0:
            security_score -= 10
        
        security_score = max(0, security_score)
        
        return {
            'success': True,
            'dashboard': {
                'active_sessions': {
                    'count': active_sessions,
                    'max_allowed': max_devices,
                    'exceeded': active_sessions > max_devices
                },
                'recent_events': events_result.data,
                'unresolved_alerts': unresolved_count,
                'trusted_devices': trusted_count,
                'security_score': security_score,
                'recommendations': _get_security_recommendations(
                    active_sessions, max_devices, unresolved_count, trusted_count
                )
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting security dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security dashboard"
        )


def _get_security_recommendations(
    active_sessions: int,
    max_devices: int,
    unresolved_count: int,
    trusted_count: int
) -> List[str]:
    """Generate security recommendations based on user's status"""
    recommendations = []
    
    if active_sessions > max_devices:
        recommendations.append("⚠️ You have exceeded your device limit. Sign out unused devices.")
    
    if unresolved_count > 0:
        recommendations.append(f"⚠️ You have {unresolved_count} security alert(s) requiring attention.")
    
    if trusted_count == 0 and active_sessions > 0:
        recommendations.append("💡 Consider marking your regular devices as trusted for faster login.")
    
    if active_sessions == 1 and trusted_count > 0:
        recommendations.append("✅ Your account security looks good!")
    
    if active_sessions == 0:
        recommendations.append("🔒 No active sessions detected. Sign in to use SAVO.")
    
    return recommendations
