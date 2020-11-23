import httpx
import ipaddress
import jwt
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from . import models, schemas
from .settings import (
    APNS_ALGORITHM,
    APNS_AUTH_KEY,
    APNS_KEY_ID,
    TEAM_ID,
    BUNDLE_ID,
    APPLE_SERVER,
    ALLOWED_NETWORKS,
    SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)


def create_access_token(
    username: str, expires_delta_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """Encode the data as JWT, including the expiration time claim"""
    expire = datetime.utcnow() + timedelta(minutes=expires_delta_minutes)
    to_encode = {"sub": username, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, str(SECRET_KEY), algorithm=JWT_ALGORITHM)
    return encoded_jwt.decode("utf-8")


def decode_access_token(encoded_token: str) -> Dict:
    return jwt.decode(encoded_token, str(SECRET_KEY), algorithms=[JWT_ALGORITHM])


def check_ips(
    ips: Optional[List[str]] = None, allowed_networks: List[str] = ALLOWED_NETWORKS
) -> bool:
    """Return True if all ip addresses are in the list of allowed networks

    Any IP is allowed if the list is empty
    """
    if not allowed_networks:
        return True
    if ips is None or not ips:
        # No IP to check
        return False
    return all([is_ip_allowed(ip, allowed_networks) for ip in ips])


def is_ip_allowed(ip: str, allowed_networks: List[str]) -> bool:
    """Return True if the ip is in the list of allowed networks

    Any IP is allowed if the list is empty
    """
    if not allowed_networks:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        # Invalid IP
        return False
    for allowed_network in allowed_networks:
        if addr in ipaddress.ip_network(allowed_network):
            return True
    return False


async def send_push_to_ios(apn: str, payload: schemas.ApnPayload) -> None:
    token = jwt.encode(
        {"iss": str(TEAM_ID), "iat": datetime.utcnow()},
        str(APNS_AUTH_KEY),
        algorithm=APNS_ALGORITHM,
        headers={"alg": APNS_ALGORITHM, "kid": str(APNS_KEY_ID)},
    )
    headers = {
        "apns-expiration": "0",
        "apns-priority": "10",
        "apns-topic": BUNDLE_ID,
        "authorization": f"Bearer {token.decode('utf-8')}",
    }
    url = f"https://{APPLE_SERVER}/3/device/{apn}"
    async with httpx.AsyncClient(http2=True) as client:
        await client.post(url, json=payload.dict(), headers=headers)


async def send_notification(notification: models.Notification) -> None:
    for user_notification in notification.users_notification:
        apn_payload = user_notification.to_apn_payload()
        for apn_token in user_notification.user.apn_tokens:
            await send_push_to_ios(apn_token, apn_payload)
