"""
ফাইলের নাম  : django_service.py
ফাইলের কাজ  : Django Backend এর সাথে সব যোগাযোগ এই file করে
               1. Leads fetch করা
               2. Call log পাঠানো
               3. Booking পাঠানো
কে use করে  : call_worker.py, webhooks.py, tools.py
সংযুক্ত     : config.py (Base URL এর জন্য)

Authentication:
→ প্রতি Business এর আলাদা X-API-Key
→ Key আসে Provision Payload থেকে
→ Memory তে store হয় business_id দিয়ে
"""

import httpx
from app import config

# ============================================
# PER-BUSINESS API KEY STORE
# কাজ : প্রতি Business এর API Key memory তে রাখে
# কখন: POST /agencies/ provision হলে save হয়
# ============================================
BUSINESS_KEYS: dict = {}
# Format: { "business_id": "fai_op_xxxx" }


def save_business_key(business_id: str, api_key: str):
    """
    কাজ  : Business এর API Key memory তে save করে
    কখন : POST /agencies/ provision এ call হয়
    """
    BUSINESS_KEYS[business_id] = api_key
    print(f"🔑 Key saved | Business: {business_id}")


def get_headers(business_id: str) -> dict:
    """
    কাজ  : Business এর X-API-Key দিয়ে headers বানায়
    নেয়  : business_id
    দেয়  : headers dict
    """
    api_key = BUSINESS_KEYS.get(business_id, "")
    return {
        "X-API-Key"   : api_key,
        "Content-Type": "application/json"
    }


# ============================================
# FETCH LEADS
# কাজ : Django থেকে pending leads আনে
# কে call করে : call_worker.py
# ============================================
async def fetch_leads(business_id: str) -> list:
    """
    কাজ  : Django এর /api/ai/leads/ থেকে leads আনে
    নেয়  : business_id
    দেয়  : leads list (max 50)
    কখন : Campaign worker leads দরকার হলে
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.DJANGO_BASE_URL}/api/ai/leads/",
                headers=get_headers(business_id),
                timeout=30
            )

        if response.status_code == 200:
            data  = response.json()
            leads = data.get("results", [])
            count = data.get("count", 0)
            print(f"📋 Leads fetched | Business: {business_id} | Count: {count}")
            return leads
        else:
            print(f"❌ Leads fetch failed | Status: {response.status_code} | {response.text}")
            return []

    except Exception as e:
        print(f"❌ Leads fetch error | {str(e)}")
        return []


# ============================================
# SEND CALL LOG
# কাজ : Call শেষে Django তে log পাঠায়
# কে call করে : webhooks.py (end-of-call-report এ)
# ============================================
async def send_call_log(business_id: str, call_log_data: dict) -> bool:
    """
    কাজ  : Call log + lead status একসাথে Django তে পাঠায়
    নেয়  : business_id, call_log_data
    দেয়  : True/False
    কখন : Call শেষ হলে

    call_log_data format:
    {
        "lead_id"    : "uuid",
        "lead_status": "done",
        "name"       : "Rahim Ahmed",
        "phone_number": "+8801711111111",
        "duration"   : "02:30",
        "status"     : "Interested",
        "summary"    : "Customer interested in health plan",
        "transcript" : [...],
        "audio_url"  : "https://..."
    }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.DJANGO_BASE_URL}/api/ai/call-logs/",
                json   = call_log_data,
                headers= get_headers(business_id),
                timeout= 30
            )

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Call log sent | Business: {business_id} | Lead: {call_log_data.get('lead_id')}")
            return True
        else:
            print(f"❌ Call log failed | Status: {response.status_code} | {response.text}")
            return False

    except Exception as e:
        print(f"❌ Call log error | {str(e)}")
        return False


# ============================================
# SEND BOOKING
# কাজ : Meeting book হলে Django তে পাঠায়
# কে call করে : tools.py (bookAppointment এ)
# ============================================
async def send_booking(business_id: str, booking_data: dict) -> bool:
    """
    কাজ  : Meeting booking Django তে পাঠায়
    নেয়  : business_id, booking_data
    দেয়  : True/False
    কখন : Customer meeting book করলে

    booking_data format:
    {
        "lead_id"       : "uuid",
        "meeting_date"  : "2026-05-20",
        "meeting_time"  : "10:00:00",
        "meeting_link"  : "https://calendly.com/...",
        "status"        : "scheduled",
        "customer_name" : "Rahim Ahmed",
        "customer_email": "rahim@email.com",
        "customer_phone": "+8801711111111"
    }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.DJANGO_BASE_URL}/api/ai/bookings/",
                json   = booking_data,
                headers= get_headers(business_id),
                timeout= 30
            )

        if response.status_code in [200, 201]:
            print(f"✅ Booking sent | Business: {business_id} | Lead: {booking_data.get('lead_id')}")
            return True
        else:
            print(f"❌ Booking failed | Status: {response.status_code} | {response.text}")
            return False

    except Exception as e:
        print(f"❌ Booking error | {str(e)}")
        return False