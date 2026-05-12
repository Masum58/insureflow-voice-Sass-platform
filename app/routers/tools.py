"""
ফাইলের নাম  : tools.py
ফাইলের কাজ  : Call চলাকালীন Vapi এর সব request handle করে
কে call করে : Vapi (call এর ভেতর থেকে automatically)
সংযুক্ত     : ghl_service.py, db_service.py
"""

from fastapi import APIRouter, Request
from app.services import db_service, ghl_service

router = APIRouter()


# ============================================
# BOOK APPOINTMENT
# কাজ : Customer meeting book করতে চাইলে
# URL : POST /tools/book-appointment
# কে call করে : Vapi (customer "meeting চাই" বললে)
# ============================================
@router.post("/book-appointment")
async def book_appointment(request: Request):
    """
    কাজ  : Customer meeting book করে
    নেয়  : customer_name, datetime, lead_id, timezone
    দেয়  : result message Vapi কে (Vapi এর format এ)
    করে  : DB তে meeting save + GHL sync
    """
    try:
        data = await request.json()
    except:
        data = {}

    customer_name = data.get("customer_name", "Customer")
    datetime_str  = data.get("datetime", "")
    lead_id       = data.get("lead_id", "")
    timezone      = data.get("timezone", "Asia/Dhaka")

    print(f"📅 Booking | Name: {customer_name} | Time: {datetime_str} | Lead: {lead_id}")

    # Meeting link (placeholder, পরে GHL Calendar দিয়ে real link আসবে)
    meeting_link = "https://calendly.com/insureflow/meeting"

    # DB তে meeting save করো
    await db_service.save_meeting({
        "lead_id"     : lead_id,
        "agency_id"   : 1,
        "meeting_link": meeting_link,
        "scheduled_at": datetime_str,
        "customer_name": customer_name
    })

    # Lead status update করো
    if lead_id:
        await db_service.update_lead(lead_id, {
            "status": "booked"
        })

    print(f"✅ Booking confirmed | {customer_name} | {datetime_str}")

    # Vapi এর জন্য সঠিক format
    return {
        "result": f"Appointment successfully booked for {customer_name} on {datetime_str}. Meeting link: {meeting_link}"
    }


# ============================================
# QUALIFY LEAD
# কাজ : Lead এর intent বোঝার পর status update করে
# URL : POST /tools/qualify-lead
# কে call করে : Vapi (intent detect হলে)
# ============================================
@router.post("/qualify-lead")
async def qualify_lead(request: Request):
    """
    কাজ  : Lead এর intent অনুযায়ী status update করে
    নেয়  : lead_id, intent, agency_id
    দেয়  : result message Vapi কে
    করে  : DB + GHL CRM update
    """
    try:
        data = await request.json()
    except:
        data = {}

    lead_id   = data.get("lead_id", "")
    intent    = data.get("intent", "")
    agency_id = data.get("agency_id", 1)

    print(f"🎯 Qualify Lead | Lead: {lead_id} | Intent: {intent}")

    # DB তে lead status update করো
    if lead_id:
        await db_service.update_lead(lead_id, {
            "status": intent
        })

    # GHL CRM update করো
    ghl_contact_id = data.get("ghl_contact_id", "")
    if ghl_contact_id:
        await ghl_service.update_contact_status(
            ghl_contact_id=ghl_contact_id,
            intent=intent,
            agency_id=agency_id
        )

    # Vapi এর জন্য সঠিক format
    return {
        "result": f"Lead status updated to {intent}"
    }


# ============================================
# GET TRANSFER NUMBER
# কাজ : Agency অনুযায়ী সঠিক agent number দেয়
# URL : POST /tools/transfer-number
# কে call করে : Vapi (transferCall এর আগে)
# ============================================
@router.post("/transfer-number")
async def get_transfer_number(request: Request):
    """
    কাজ  : Agency র আলাদা agent number দেয় Vapi কে
    নেয়  : agency_id
    দেয়  : transfer number
    করে  : DB থেকে agency র number আনে
    """
    try:
        data = await request.json()
    except:
        data = {}

    agency_id = data.get("agency_id", 1)

    print(f"📞 Transfer number | Agency: {agency_id}")

    # DB থেকে agency র transfer number আনো
    agency = await db_service.get_agency(agency_id)
    transfer_number = agency.get("transfer_number", "+8801322158015")

    print(f"✅ Transfer to: {transfer_number}")

    # Vapi এর জন্য সঠিক format
    return {
        "result": f"Transfer to {transfer_number}",
        "transfer_number": transfer_number
    }


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def tools_test():
    return {
        "router": "tools",
        "status": "ready",
        "endpoints": [
            "POST /tools/book-appointment",
            "POST /tools/qualify-lead",
            "POST /tools/transfer-number"
        ]
    }