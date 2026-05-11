"""
ফাইলের নাম  : ghl_service.py
ফাইলের কাজ  : GoHighLevel CRM এর সাথে সব যোগাযোগ এই file করে
               1. Call শেষে lead status update
               2. Call notes CRM এ add করা
               3. নতুন Contact তৈরি করা
               4. Meeting/Appointment sync করা
কে use করে  : webhooks.py (call শেষে automatically)
               tools.py (booking হলে)
সংযুক্ত     : config.py (GHL API Key এর জন্য)

NOTE: GHL API Key না থাকলে সব function skip করবে
      GHL ready হলে .env তে GHL_API_KEY দাও
"""

import httpx
from app import config


# ============================================
# GHL API KEY CHECK
# কাজ : GHL API Key আছে কিনা check করে
# ============================================
def is_ghl_configured():
    """
    কাজ  : GHL API Key set আছে কিনা check করে
    দেয়  : True/False
    """
    return (
        config.GHL_API_KEY is not None and
        config.GHL_API_KEY != "your_ghl_api_key_here" and
        config.GHL_API_KEY != ""
    )


# ============================================
# GHL CLIENT HEADERS
# কাজ : GHL API তে request পাঠানোর জন্য
# ============================================
def get_ghl_headers():
    """
    কাজ  : GHL API request এর জন্য headers বানায়
    দেয়  : Authorization header সহ dict
    """
    return {
        "Authorization": f"Bearer {config.GHL_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }


# ============================================
# UPDATE CONTACT STATUS
# কাজ : Call শেষে GHL তে lead এর status update করে
# কে call করে : webhooks.py (call ended event এ)
# ============================================
async def update_contact_status(
    ghl_contact_id: str,
    intent: str,
    agency_id: int
):
    """
    কাজ  : GHL CRM এ lead এর status/tag update করে
    নেয়  : ghl_contact_id, intent, agency_id
    দেয়  : True (success) / False (failure)
    কখন : Call শেষ হলে intent বোঝার পর

    Intent → GHL Tag mapping:
    interested     → Qualified
    not_interested → Not Interested
    busy           → Follow Up
    talk_to_agent  → Transferred to Agent
    """

    # GHL Key নেই → skip
    if not is_ghl_configured():
        print(f"⚠️ GHL: API Key নেই, skipping update | Contact: {ghl_contact_id}")
        return True

    # Intent → GHL Tag
    intent_tag_map = {
        "interested":     "Qualified",
        "not_interested": "Not Interested",
        "busy":           "Follow Up",
        "talk_to_agent":  "Transferred to Agent"
    }
    tag = intent_tag_map.get(intent, "Contacted")

    print(f"📊 GHL: Updating contact | ID: {ghl_contact_id} | Tag: {tag}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{config.GHL_BASE_URL}/contacts/{ghl_contact_id}",
                json={"tags": [tag]},
                headers=get_ghl_headers(),
                timeout=30
            )

        if response.status_code == 200:
            print(f"✅ GHL: Contact updated | ID: {ghl_contact_id}")
            return True
        else:
            print(f"❌ GHL: Update failed | Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ GHL: Exception | {str(e)}")
        return False


# ============================================
# ADD CALL NOTE
# কাজ : Call এর summary GHL Contact এ note হিসেবে add করে
# কে call করে : webhooks.py (call ended event এ)
# ============================================
async def add_call_note(
    ghl_contact_id: str,
    call_summary: str,
    duration_seconds: int,
    intent: str
):
    """
    কাজ  : GHL CRM এ call এর note add করে
    নেয়  : ghl_contact_id, call_summary, duration_seconds, intent
    দেয়  : True (success) / False (failure)
    কখন : Call শেষ হলে transcript সহ
    """

    # GHL Key নেই → skip
    if not is_ghl_configured():
        print(f"⚠️ GHL: API Key নেই, skipping note | Contact: {ghl_contact_id}")
        return True

    # Note বানাও
    minutes = duration_seconds // 60
    seconds = duration_seconds % 60

    note_body = f"""
📞 AI Call Summary
──────────────────
Duration : {minutes}m {seconds}s
Intent   : {intent}
──────────────────
{call_summary}
    """

    print(f"📝 GHL: Adding note | Contact: {ghl_contact_id} | Duration: {minutes}m {seconds}s")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.GHL_BASE_URL}/contacts/{ghl_contact_id}/notes",
                json={"body": note_body},
                headers=get_ghl_headers(),
                timeout=30
            )

        if response.status_code == 201:
            print(f"✅ GHL: Note added | Contact: {ghl_contact_id}")
            return True
        else:
            print(f"❌ GHL: Note failed | Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ GHL: Exception | {str(e)}")
        return False


# ============================================
# CREATE CONTACT
# কাজ : Inbound call এ নতুন customer এলে GHL এ contact বানায়
# কে call করে : webhooks.py (inbound call started এ)
# ============================================
async def create_contact(
    name: str,
    phone: str,
    agency_id: int
):
    """
    কাজ  : GHL CRM এ নতুন contact তৈরি করে
    নেয়  : name, phone, agency_id
    দেয়  : ghl_contact_id (নতুন contact এর ID)
    কখন : Inbound call এ নতুন customer এলে
    """

    # GHL Key নেই → placeholder return
    if not is_ghl_configured():
        print(f"⚠️ GHL: API Key নেই, skipping contact create | Phone: {phone}")
        return f"placeholder_contact_{phone}"

    print(f"👤 GHL: Creating contact | Name: {name} | Phone: {phone}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.GHL_BASE_URL}/contacts",
                json={
                    "name": name,
                    "phone": phone,
                    "tags": ["AI Inbound Call"]
                },
                headers=get_ghl_headers(),
                timeout=30
            )

        if response.status_code == 201:
            contact_id = response.json().get("contact", {}).get("id")
            print(f"✅ GHL: Contact created | ID: {contact_id}")
            return contact_id
        else:
            print(f"❌ GHL: Contact creation failed | Error: {response.text}")
            return None

    except Exception as e:
        print(f"❌ GHL: Exception | {str(e)}")
        return None


# ============================================
# SYNC MEETING
# কাজ : Meeting book হলে GHL এ note add করে
# কে call করে : tools.py (bookAppointment হলে)
# ============================================
async def sync_meeting(
    ghl_contact_id: str,
    meeting_link: str,
    scheduled_at: str,
    customer_name: str
):
    """
    কাজ  : Booked meeting GHL এ note হিসেবে add করে
    নেয়  : ghl_contact_id, meeting_link, scheduled_at, customer_name
    দেয়  : True (success) / False (failure)
    কখন : bookAppointment tool call হলে
    """

    # GHL Key নেই → skip
    if not is_ghl_configured():
        print(f"⚠️ GHL: API Key নেই, skipping meeting sync | Contact: {ghl_contact_id}")
        return True

    note_body = f"""
📅 Meeting Booked via AI
────────────────────────
Customer  : {customer_name}
Scheduled : {scheduled_at}
Link      : {meeting_link}
────────────────────────
Booked automatically by InsureFlow AI
    """

    print(f"📅 GHL: Syncing meeting | Contact: {ghl_contact_id} | Time: {scheduled_at}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.GHL_BASE_URL}/contacts/{ghl_contact_id}/notes",
                json={"body": note_body},
                headers=get_ghl_headers(),
                timeout=30
            )

        if response.status_code == 201:
            print(f"✅ GHL: Meeting synced | Contact: {ghl_contact_id}")
            return True
        else:
            print(f"❌ GHL: Sync failed | Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ GHL: Exception | {str(e)}")
        return False