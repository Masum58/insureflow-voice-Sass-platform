"""
ফাইলের নাম  : tools.py
ফাইলের কাজ  : Call চলাকালীন Vapi এর সব request handle করে
কে call করে : Vapi (call এর ভেতর থেকে automatically)
সংযুক্ত     : ghl_service.py, db_service.py
"""

from fastapi import APIRouter, Request
#from app.services import db_service, ghl_service, calendly_service
from app.services import db_service, calendly_service

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
    করে  : DB তে meeting save + Calendly sync
    """
    try:
        data = await request.json()
    except:
        data = {}

    customer_name = data.get("customer_name", "Customer")
    datetime_str  = data.get("datetime", "") # ISO format expected for Calendly
    lead_id       = data.get("lead_id", "")
    timezone      = data.get("timezone", "Asia/Dhaka")

    print(f"📅 Booking | Name: {customer_name} | Time: {datetime_str} | Lead: {lead_id}")

    # Lead এর email নিয়ে আসো DB থেকে
    lead = await db_service.get_lead(lead_id)
    email = lead.get("email", "test@example.com") if lead else "test@example.com"

    # Step 1 — Calendly তে বুক করো
    calendly_res = await calendly_service.create_invitee(
        customer_name=customer_name,
        email=email,
        start_time=datetime_str,
        timezone=timezone
    )

    # Meeting link (Calendly থেকে আসলে সেটি ইউজ করব, নাহলে প্লেসহোল্ডার)
    meeting_link = "https://calendly.com/insureflow/meeting"
    if calendly_res:
        # Calendly response থেকে link নেওয়ার চেষ্টা
        meeting_link = calendly_res.get("resource", {}).get("scheduling_url", meeting_link)

    # Step 2 — DB তে meeting save করো
    await db_service.save_meeting({
        "lead_id"     : lead_id,
        "agency_id"   : 1,
        "meeting_link": meeting_link,
        "scheduled_at": datetime_str,
        "customer_name": customer_name
    })

    # Step 3 — Lead status update করো
    if lead_id:
        await db_service.update_lead(lead_id, {
            "status": "booked"
        })

    print(f"✅ Booking confirmed | {customer_name} | {datetime_str}")

    # Vapi এর জন্য সঠিক format
    return {
        "result": f"Appointment successfully booked for {customer_name} on {datetime_str}. A calendar invitation has been sent to {email}."
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
    """
    # GHL CRM update করো
    ghl_contact_id = data.get("ghl_contact_id", "")
    if ghl_contact_id:
        await ghl_service.update_contact_status(
            ghl_contact_id=ghl_contact_id,
            intent=intent,
            agency_id=agency_id
        )"""

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
# HANDLE TOOL CALLS (CENTRAL HANDLER)
# কাজ : Vapi থেকে আসা সব tool request handle করে
# কখন: AI কোনো tool use করতে চাইলে Vapi এই event পাঠায়
# ============================================
async def handle_tool_calls(message: dict):
    """
    কাজ  : Tool call এর type দেখে সঠিক logic run করে
    নেয়  : message object (Vapi থেকে)
    দেয়  : Tool call result
    """
    tool_calls = message.get("toolCalls", [])
    if not tool_calls:
        return {"results": []}

    # Extract dynamic agency_id from payload
    call = message.get("call") or {}
    phone_obj = message.get("phoneNumber") or {}
    called_number = phone_obj.get("number", "")
    
    agency_id = None
    if called_number:
        from app.services import db_service
        try:
            agency_id = await db_service.get_agency_id_by_phone(called_number)
        except:
            pass
            
    if not agency_id:
        metadata = call.get("metadata") or {}
        agency_id = metadata.get("agency_id", 1)

    results = []

    for tool_call in tool_calls:
        tool_id = tool_call.get("id")
        function = tool_call.get("function", {})
        name = function.get("name")
        args = function.get("arguments", {})

        print(f"🛠️ Tool Call | Name: {name} | ID: {tool_id} | Agency: {agency_id}")

        # --- CASE 1: Book Appointment (Calendly) ---
        if name == "bookAppointment":
            customer_name = args.get("customer_name", "Customer")
            datetime_str  = args.get("datetime", "")
            lead_id       = args.get("lead_id", "1")
            
            res = await book_appointment_internal(customer_name, datetime_str, lead_id)
            results.append({"toolCallId": tool_id, "result": res})

        # --- CASE 2: Search Knowledge Base (Dynamic RAG) ---
        elif name == "searchKnowledgeBase":
            query = args.get("query", "")
            tool_agency_id = args.get("agency_id", agency_id)
            
            print(f"🔍 RAG Tool Search | Query: {query} | Agency: {tool_agency_id}")
            from app.services import rag_service
            res = await rag_service.build_context(agency_id=tool_agency_id, query=query)
            
            results.append({
                "toolCallId": tool_id, 
                "result": res if res else "No specific information found in the records."
            })

        # --- CASE 3: Transfer Call ---
        elif name == "transferCall":
            tool_agency_id = args.get("agency_id", agency_id)
            agency = await db_service.get_agency(tool_agency_id)
            transfer_number = agency.get("transfer_number", "+8801322158015")
            
            results.append({
                "toolCallId": tool_id,
                "result": f"Transferring to {transfer_number}",
                "transfer_number": transfer_number
            })

        # --- DEFAULT CASE ---
        else:
            results.append({
                "toolCallId": tool_id,
                "result": f"Tool {name} not found or not implemented."
            })

    return {"results": results}



# ============================================
# INTERNAL HELPERS
# ============================================

async def book_appointment_internal(customer_name: str, datetime_str: str, lead_id: str):
    """
    কাজ  : সরাসরি Calendly এবং DB তে বুকিং দেয়
    """
    try:
        # Lead এর email নাও
        lead = await db_service.get_lead(lead_id)
        email = lead.get("email", "customer@example.com") if lead else "customer@example.com"

        # Calendly API কল
        calendly_res = await calendly_service.create_invitee(
            customer_name=customer_name,
            email=email,
            start_time=datetime_str
        )

        meeting_link = "https://calendly.com/insureflow/meeting"
        if calendly_res:
             meeting_link = calendly_res.get("resource", {}).get("scheduling_url", meeting_link)

        # DB তে সেভ করো
        await db_service.save_meeting({
            "lead_id"     : lead_id,
            "agency_id"   : 1,
            "meeting_link": meeting_link,
            "scheduled_at": datetime_str,
            "customer_name": customer_name
        })

        return f"Successfully booked for {customer_name} on {datetime_str}."

    except Exception as e:
        print(f"❌ Booking Error: {str(e)}")
        return "Failed to book appointment. Please try again later."


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def tools_test():
    return {
        "router": "tools",
        "status": "ready"
    }