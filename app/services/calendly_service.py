"""
ফাইলের নাম  : calendly_service.py
ফাইলের কাজ  : Calendly API এর সাথে যোগাযোগ করে মিটিং বুক করে
কে use করে  : tools.py
সংযুক্ত     : config.py
"""

import httpx
from app import config
from datetime import datetime

def get_calendly_headers():
    """
    কাজ  : Calendly API এর জন্য headers বানায়
    """
    return {
        "Authorization": f"Bearer {config.CALENDLY_API_KEY}",
        "Content-Type": "application/json"
    }

async def create_invitee(customer_name: str, email: str, start_time: str, timezone: str = "Asia/Dhaka"):
    """
    কাজ  : Calendly তে একজন নতুন invitee (মিটিং) তৈরি করে
    নেয়  : customer_name, email, start_time (ISO format), timezone
    দেয়  : response json
    """
    
    if not config.CALENDLY_API_KEY or not config.CALENDLY_EVENT_TYPE_URI:
        print("⚠️ Calendly API Key or Event Type URI missing!")
        return None

    payload = {
        "event_type": config.CALENDLY_EVENT_TYPE_URI,
        "start_time": start_time,
        "email": email,
        "timezone": timezone,
        "name": customer_name
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.CALENDLY_BASE_URL}/invitees",
            json=payload,
            headers=get_calendly_headers(),
            timeout=30
        )

    if response.status_code == 201:
        print(f"✅ Calendly booking successful for {customer_name}")
        return response.json()
    else:
        print(f"❌ Calendly booking failed | Status: {response.status_code} | Error: {response.text}")
        return None

async def get_user_event_types():
    """
    কাজ  : ইউজারের সব event types নিয়ে আসে (URI খুঁজে পেতে সাহায্য করে)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.CALENDLY_BASE_URL}/event_types",
            params={"user": "https://api.calendly.com/users/me"}, # অথবা খালি রাখা যায় যদি PAT ইউজ করা হয়
            headers=get_calendly_headers(),
            timeout=30
        )
    return response.json() if response.status_code == 200 else None
