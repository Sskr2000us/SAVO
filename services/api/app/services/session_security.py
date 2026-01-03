"""
Session Security Service - Device Limit Enforcement & Tracking
Prevents credential sharing with 2-device limit and security monitoring
Phase 1: Immediate - Hard security controls
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, status
import httpx
from app.core.database import get_supabase_client

logger = logging.getLogger(__name__)

# Constants
MAX_DEVICES_DEFAULT = 2
MIN_DISTANCE_MILES_SUSPICIOUS = 50  # Flag concurrent sessions >50 miles apart
IP_GEOLOCATION_API = "http://ip-api.com/json/"  # Free tier: 45 req/min


class SessionSecurityService:
    """Handles device fingerprinting, session tracking, and security enforcement"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def track_login(
        self,
        user_id: str,
        session_token: str,
        request: Request
    ) -> Dict[str, Any]:
        """
        Track new login attempt with device fingerprinting and IP location.
        Returns session info or raises HTTPException if device limit exceeded.
        """
        try:
            # 1. Extract device fingerprint and IP info
            device_info = await self._extract_device_info(request)
            location_info = await self._get_ip_location(device_info['ip_address'])
            
            # 2. Check device limit BEFORE allowing login
            can_login = await self._check_device_limit(user_id)
            if not can_login:
                # Log blocked attempt
                await self._log_security_event(
                    user_id=user_id,
                    event_type='login_blocked',
                    severity='critical',
                    ip_address=device_info['ip_address'],
                    device_info=device_info['device_os'],
                    location=f"{location_info.get('city', 'Unknown')}, {location_info.get('country', 'Unknown')}",
                    description=f"Login blocked: Device limit ({MAX_DEVICES_DEFAULT}) exceeded",
                    action_taken='blocked'
                )
                
                # Queue email notification
                await self._queue_security_email(
                    user_id=user_id,
                    notification_type='device_limit_reached',
                    context={
                        'device': device_info['device_os'],
                        'location': location_info.get('city', 'Unknown'),
                        'ip': device_info['ip_address']
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "device_limit_exceeded",
                        "message": f"Maximum {MAX_DEVICES_DEFAULT} devices allowed. Sign out other devices first.",
                        "max_devices": MAX_DEVICES_DEFAULT,
                        "help": "Go to Settings → Device Security to manage your devices"
                    }
                )
            
            # 3. Create session token hash
            token_hash = self._hash_token(session_token)
            
            # 4. Check if device is trusted
            is_trusted = await self._is_trusted_device(user_id, device_info['fingerprint'])
            
            # 5. Insert/update session record
            session_data = {
                'user_id': user_id,
                'session_token_hash': token_hash,
                'device_type': device_info['device_type'],
                'device_os': device_info['device_os'],
                'device_model': device_info['device_model'],
                'browser': device_info['browser'],
                'user_agent': device_info['user_agent'],
                'device_fingerprint': device_info['fingerprint'],
                'ip_address': device_info['ip_address'],
                'country_code': location_info.get('countryCode'),
                'country_name': location_info.get('country'),
                'region': location_info.get('regionName'),
                'city': location_info.get('city'),
                'latitude': location_info.get('lat'),
                'longitude': location_info.get('lon'),
                'timezone': location_info.get('timezone'),
                'isp_name': location_info.get('isp'),
                'is_active': True,
                'is_current': True,
                'is_trusted': is_trusted,
                'last_active_at': datetime.utcnow().isoformat()
            }
            
            # Upsert session (handle re-login from same device)
            result = self.supabase.table('user_sessions').upsert(
                session_data,
                on_conflict='user_id,session_token_hash'
            ).execute()
            
            session_id = result.data[0]['id'] if result.data else None
            
            # 6. Check for suspicious concurrent locations
            await self._check_concurrent_locations(user_id, session_id)
            
            # 7. Check if new/unrecognized device
            if not is_trusted:
                await self._handle_new_device_login(
                    user_id=user_id,
                    device_info=device_info,
                    location_info=location_info
                )
            
            # 8. Log successful login
            await self._log_security_event(
                user_id=user_id,
                event_type='login_success',
                severity='info',
                ip_address=device_info['ip_address'],
                device_info=device_info['device_os'],
                location=f"{location_info.get('city', 'Unknown')}, {location_info.get('country', 'Unknown')}",
                description=f"Successful login from {device_info['device_os']}",
                action_taken='allowed'
            )
            
            return {
                'success': True,
                'session_id': session_id,
                'device_recognized': is_trusted,
                'location': location_info.get('city'),
                'active_devices': await self._get_active_session_count(user_id)
            }
            
        except HTTPException:
            raise  # Re-raise device limit errors
        except Exception as e:
            logger.error(f"Error tracking login: {e}")
            # Don't fail login on tracking errors - security logging is non-critical
            return {'success': False, 'error': str(e)}
    
    async def revoke_session(self, user_id: str, session_id: str) -> bool:
        """Revoke a specific session"""
        try:
            result = self.supabase.table('user_sessions').update({
                'is_active': False,
                'revoked_at': datetime.utcnow().isoformat()
            }).eq('id', session_id).eq('user_id', user_id).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return False
    
    async def revoke_other_sessions(self, user_id: str, current_token_hash: str) -> int:
        """Revoke all sessions except current"""
        try:
            # Use the SQL function
            result = self.supabase.rpc(
                'revoke_other_sessions',
                {
                    'p_user_id': user_id,
                    'p_current_session_hash': current_token_hash
                }
            ).execute()
            
            revoked_count = result.data if result.data else 0
            
            # Log event
            await self._log_security_event(
                user_id=user_id,
                event_type='force_signout_all',
                severity='warning',
                description=f"User signed out {revoked_count} other device(s)",
                action_taken='force_logout'
            )
            
            return revoked_count
        except Exception as e:
            logger.error(f"Error revoking other sessions: {e}")
            return 0
    
    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        try:
            result = self.supabase.table('user_sessions').select('*').eq(
                'user_id', user_id
            ).eq('is_active', True).is_('signed_out_at', 'null').is_(
                'revoked_at', 'null'
            ).order('last_active_at', desc=True).execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def update_session_activity(self, session_token: str) -> bool:
        """Update last_active_at for a session (called on each API request)"""
        try:
            token_hash = self._hash_token(session_token)
            
            result = self.supabase.table('user_sessions').update({
                'last_active_at': datetime.utcnow().isoformat()
            }).eq('session_token_hash', token_hash).eq('is_active', True).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False
    
    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================
    
    async def _check_device_limit(self, user_id: str) -> bool:
        """Check if user can log in (hasn't exceeded device limit)"""
        try:
            result = self.supabase.rpc(
                'check_device_limit',
                {'p_user_id': user_id}
            ).execute()
            
            return result.data if result.data is not None else True
        except Exception as e:
            logger.error(f"Error checking device limit: {e}")
            return True  # Allow login on error
    
    async def _get_active_session_count(self, user_id: str) -> int:
        """Get count of active sessions"""
        try:
            result = self.supabase.rpc(
                'get_active_session_count',
                {'p_user_id': user_id}
            ).execute()
            
            return result.data if result.data else 0
        except Exception as e:
            logger.error(f"Error getting session count: {e}")
            return 0
    
    async def _extract_device_info(self, request: Request) -> Dict[str, Any]:
        """Extract device fingerprint from request"""
        user_agent = request.headers.get('user-agent', 'Unknown')
        ip_address = self._get_client_ip(request)
        
        # Parse user agent (basic implementation)
        device_type = 'web'
        device_os = 'Unknown'
        browser = 'Unknown'
        device_model = 'Browser'
        
        ua_lower = user_agent.lower()
        
        # Detect mobile/tablet
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device_type = 'mobile'
        elif 'ipad' in ua_lower or 'tablet' in ua_lower:
            device_type = 'tablet'
        else:
            device_type = 'desktop'
        
        # Detect OS
        if 'windows' in ua_lower:
            device_os = 'Windows'
        elif 'mac os' in ua_lower or 'macos' in ua_lower:
            device_os = 'macOS'
        elif 'iphone' in ua_lower:
            device_os = 'iOS'
            device_model = 'iPhone'
        elif 'ipad' in ua_lower:
            device_os = 'iOS'
            device_model = 'iPad'
        elif 'android' in ua_lower:
            device_os = 'Android'
        elif 'linux' in ua_lower:
            device_os = 'Linux'
        
        # Detect browser
        if 'chrome' in ua_lower and 'edg' not in ua_lower:
            browser = 'Chrome'
        elif 'firefox' in ua_lower:
            browser = 'Firefox'
        elif 'safari' in ua_lower and 'chrome' not in ua_lower:
            browser = 'Safari'
        elif 'edg' in ua_lower:
            browser = 'Edge'
        
        # Create device fingerprint (composite of multiple factors)
        fingerprint_string = f"{device_os}|{browser}|{ip_address}|{user_agent[:50]}"
        fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
        
        return {
            'device_type': device_type,
            'device_os': device_os,
            'device_model': device_model,
            'browser': browser,
            'user_agent': user_agent,
            'ip_address': ip_address,
            'fingerprint': fingerprint
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request headers"""
        # Check common proxy headers
        forwarded = request.headers.get('x-forwarded-for')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return 'Unknown'
    
    async def _get_ip_location(self, ip_address: str) -> Dict[str, Any]:
        """Get geolocation info from IP address using free API"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{IP_GEOLOCATION_API}{ip_address}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return data
                
                return {}
        except Exception as e:
            logger.warning(f"Error getting IP location: {e}")
            return {}
    
    def _hash_token(self, token: str) -> str:
        """Create hash of session token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()[:32]
    
    async def _is_trusted_device(self, user_id: str, fingerprint: str) -> bool:
        """Check if device fingerprint is in trusted devices"""
        try:
            result = self.supabase.table('trusted_devices').select('id').eq(
                'user_id', user_id
            ).eq('device_fingerprint', fingerprint).eq('is_active', True).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking trusted device: {e}")
            return False
    
    async def _check_concurrent_locations(self, user_id: str, current_session_id: str):
        """Detect if user is logged in from multiple distant locations simultaneously"""
        try:
            result = self.supabase.rpc(
                'detect_concurrent_locations',
                {
                    'p_user_id': user_id,
                    'p_min_distance_miles': MIN_DISTANCE_MILES_SUSPICIOUS
                }
            ).execute()
            
            if result.data and len(result.data) > 0:
                for concurrent in result.data:
                    distance = concurrent.get('distance_miles', 0)
                    
                    # Log suspicious concurrent location
                    await self._log_security_event(
                        user_id=user_id,
                        event_type='concurrent_location_detected',
                        severity='critical',
                        description=f"Concurrent logins detected {distance:.0f} miles apart: {concurrent.get('location1')} and {concurrent.get('location2')}",
                        action_taken='alert_sent',
                        metadata={
                            'distance_miles': float(distance),
                            'location1': concurrent.get('location1'),
                            'location2': concurrent.get('location2')
                        }
                    )
                    
                    # Queue email alert
                    await self._queue_security_email(
                        user_id=user_id,
                        notification_type='concurrent_location',
                        context={
                            'distance': f"{distance:.0f} miles",
                            'location1': concurrent.get('location1'),
                            'location2': concurrent.get('location2')
                        }
                    )
                    
                    # Mark both sessions as suspicious
                    self.supabase.table('user_sessions').update({
                        'is_suspicious': True,
                        'suspicious_reason': f"Concurrent login {distance:.0f} miles apart"
                    }).in_('id', [concurrent.get('session1_id'), concurrent.get('session2_id')]).execute()
        
        except Exception as e:
            logger.error(f"Error checking concurrent locations: {e}")
    
    async def _handle_new_device_login(
        self,
        user_id: str,
        device_info: Dict[str, Any],
        location_info: Dict[str, Any]
    ):
        """Handle login from new/unrecognized device"""
        try:
            # Log new device event
            await self._log_security_event(
                user_id=user_id,
                event_type='new_device_detected',
                severity='warning',
                ip_address=device_info['ip_address'],
                device_info=device_info['device_os'],
                location=f"{location_info.get('city', 'Unknown')}, {location_info.get('country', 'Unknown')}",
                description=f"Login from new device: {device_info['device_os']} - {device_info['browser']}",
                action_taken='email_sent',
                requires_user_action=True
            )
            
            # Queue email notification
            await self._queue_security_email(
                user_id=user_id,
                notification_type='new_device_login',
                context={
                    'device': f"{device_info['device_os']} - {device_info['browser']}",
                    'location': f"{location_info.get('city', 'Unknown')}, {location_info.get('country', 'Unknown')}",
                    'ip': device_info['ip_address'],
                    'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
                }
            )
        except Exception as e:
            logger.error(f"Error handling new device login: {e}")
    
    async def _log_security_event(
        self,
        user_id: str,
        event_type: str,
        severity: str = 'info',
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        action_taken: Optional[str] = None,
        requires_user_action: bool = False,
        metadata: Optional[Dict] = None
    ):
        """Log security event to database"""
        try:
            event_data = {
                'user_id': user_id,
                'event_type': event_type,
                'severity': severity,
                'ip_address': ip_address,
                'device_info': device_info,
                'location': location,
                'description': description,
                'action_taken': action_taken,
                'requires_user_action': requires_user_action,
                'metadata': metadata
            }
            
            self.supabase.table('security_events').insert(event_data).execute()
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
    
    async def _queue_security_email(
        self,
        user_id: str,
        notification_type: str,
        context: Dict[str, Any]
    ):
        """Queue security notification email"""
        try:
            # Get user email
            user_result = self.supabase.table('users').select('email, full_name').eq('id', user_id).execute()
            if not user_result.data:
                return
            
            user = user_result.data[0]
            email = user.get('email')
            name = user.get('full_name') or 'SAVO User'
            
            # Generate email content based on type
            subject, body = self._generate_email_content(notification_type, name, context)
            
            notification_data = {
                'user_id': user_id,
                'notification_type': notification_type,
                'email': email,
                'subject': subject,
                'body_text': body,
                'event_context': context,
                'status': 'pending'
            }
            
            self.supabase.table('security_notifications').insert(notification_data).execute()
        except Exception as e:
            logger.error(f"Error queuing security email: {e}")
    
    def _generate_email_content(
        self,
        notification_type: str,
        user_name: str,
        context: Dict[str, Any]
    ) -> tuple[str, str]:
        """Generate email subject and body"""
        if notification_type == 'new_device_login':
            subject = "🔐 New Device Login Detected - SAVO"
            body = f"""Hi {user_name},

We detected a login to your SAVO account from a new device:

Device: {context.get('device', 'Unknown')}
Location: {context.get('location', 'Unknown')}
IP Address: {context.get('ip', 'Unknown')}
Time: {context.get('time', 'Unknown')}

Was this you?
If yes, you can ignore this email.
If no, please secure your account immediately:
1. Go to Settings → Device Security
2. Sign out all other devices
3. Change your password

Questions? Reply to this email.

- The SAVO Team
"""
        
        elif notification_type == 'device_limit_reached':
            subject = "⚠️ Device Limit Reached - SAVO"
            body = f"""Hi {user_name},

Someone tried to log into your SAVO account, but the login was blocked because you've reached the maximum device limit (2 devices).

Attempted login:
Device: {context.get('device', 'Unknown')}
Location: {context.get('location', 'Unknown')}

To allow this device:
1. Go to Settings → Device Security
2. Sign out unused devices
3. Try logging in again

- The SAVO Team
"""
        
        elif notification_type == 'concurrent_location':
            subject = "🚨 SECURITY ALERT: Suspicious Activity Detected - SAVO"
            body = f"""Hi {user_name},

⚠️ URGENT: We detected your account being used in two different locations at the same time:

Location 1: {context.get('location1', 'Unknown')}
Location 2: {context.get('location2', 'Unknown')}
Distance: {context.get('distance', 'Unknown')}

This may indicate unauthorized account access.

IMMEDIATE ACTION REQUIRED:
1. Go to Settings → Device Security
2. Review active devices
3. Sign out all other devices
4. Change your password

Questions? Contact support@savo.app

- The SAVO Security Team
"""
        
        else:
            subject = "🔐 Security Alert - SAVO"
            body = f"""Hi {user_name},

We detected unusual activity on your SAVO account.

Please review your account security at Settings → Device Security.

- The SAVO Team
"""
        
        return subject, body


# Singleton instance
_session_security_service = None

def get_session_security_service() -> SessionSecurityService:
    """Get singleton instance of SessionSecurityService"""
    global _session_security_service
    if _session_security_service is None:
        _session_security_service = SessionSecurityService()
    return _session_security_service
