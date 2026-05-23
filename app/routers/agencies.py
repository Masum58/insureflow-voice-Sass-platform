"""
ফাইলের নাম  : agencies.py
ফাইলের কাজ  : Django Backend থেকে আসা Provision request handle করে
               1. POST /agencies/       → নতুন Agency provision
               2. PATCH /agencies/{id}/ → Config update

কে call করে : Django Backend (automatically)
সংযুক্ত     : django_service.py, vapi_service.py, rag_service.py
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services import vapi_service, rag_service
from app.services import django_service

router = APIRouter()


# ============================================
# REQUEST MODELS
# ============================================
class TwilioConfig(BaseModel):
    twilio_sid   : str
    twilio_token : str
    twilio_number: str

class VoiceConfig(BaseModel):
    gender           : str = "female"
    tone             : str = "professional"
    voice_template_url: Optional[str] = None

class KnowledgeFile(BaseModel):
    id       : str
    name     : Optional[str] = ""
    file_url : str
    file_type: str
    action   : Optional[str] = "add"  # add / remove

class ProvisionRequest(BaseModel):
    business_id              : str
    business_name            : str
    api_key                  : str
    address                  : Optional[str] = ""
    open_time                : Optional[str] = None
    close_time               : Optional[str] = None
    off_days                 : Optional[List[str]] = []
    human_agent_phone        : Optional[str] = ""
    is_active                : bool = True
    active_subscription_status: str = "active"
    twilio                   : TwilioConfig
    voice                    : Optional[VoiceConfig] = None
    knowledge_files          : Optional[List[KnowledgeFile]] = []

class PatchRequest(BaseModel):
    twilio         : Optional[TwilioConfig] = None
    voice          : Optional[VoiceConfig] = None
    knowledge_files: Optional[List[KnowledgeFile]] = []


# ============================================
# In-memory Agency Store
# DB Partner ready হলে real DB তে save করবো
# ============================================
AGENCY_STORE: dict = {}
# Format: { business_id: { vapi_assistant_id, vapi_phone_number_id, ... } }


# ============================================
# POST /agencies/
# কাজ : নতুন Agency Provision করে
# কে call করে : Django Backend (auto)
# ============================================
@router.post("/")
async def provision_agency(request: ProvisionRequest):
    """
    কাজ  : Django থেকে Provision payload নিয়ে সব setup করে
    করে  :
    Step 1 → API Key save করে
    Step 2 → Twilio → Vapi তে import করে (phone_number_id পায়)
    Step 3 → Vapi Assistant create করে
    Step 4 → Knowledge Files download → Pinecone এ save করে
    Step 5 → Response দেয়
    """

    print(f"\n🏢 Provision | Business: {request.business_id} | Name: {request.business_name}")

    errors = []

    # ============================================
    # Step 1 — API Key Save করো
    # ============================================
    django_service.save_business_key(request.business_id, request.api_key)
    print(f"✅ Step 1: API Key saved")

    # ============================================
    # Step 2 — Twilio Number → Vapi তে Import করো
    # ============================================
    print(f"📞 Step 2: Importing Twilio number to Vapi...")
    vapi_phone_number_id = await vapi_service.import_twilio_number(
        twilio_sid    = request.twilio.twilio_sid,
        twilio_token  = request.twilio.twilio_token,
        twilio_number = request.twilio.twilio_number,
        business_name = request.business_name
    )

    if not vapi_phone_number_id:
        errors.append("Twilio number import failed")
        print(f"❌ Step 2: Twilio import failed")
    else:
        print(f"✅ Step 2: Phone Number ID: {vapi_phone_number_id}")

    # ============================================
    # Step 3 — Vapi Assistant Create করো
    # ============================================
    print(f"🤖 Step 3: Creating Vapi Assistant...")
    assistant_id, book_tool_id, transfer_tool_id = await vapi_service.create_agency_assistant(
        agency_id      = request.business_id,
        agency_name    = request.business_name,
        business_type  = "insurance",
        custom_prompt  = "",
        transfer_number= request.human_agent_phone or "",
        welcome_message= f"Hello! Welcome to {request.business_name}. How can I help you?"
    )

    if not assistant_id:
        errors.append("Vapi Assistant creation failed")
        print(f"❌ Step 3: Assistant creation failed")
    else:
        print(f"✅ Step 3: Assistant ID: {assistant_id}")

    # ============================================
    # Step 4 — Knowledge Files Download + Pinecone
    # ============================================
    print(f"📚 Step 4: Processing knowledge files...")
    for kf in request.knowledge_files:
        try:
            print(f"   Downloading: {kf.name} ({kf.file_type})")
            async with httpx.AsyncClient() as client:
                file_response = await client.get(kf.file_url, timeout=60)

            if file_response.status_code == 200:
                # File content থেকে text extract করো
                from app.services.file_parser import parse_file_content
                text = parse_file_content(
                    content  = file_response.content,
                    file_name= kf.name or kf.id,
                    file_type= kf.file_type
                )

                if text:
                    # Pinecone তে ingest করো
                    await rag_service.ingest_document(
                        agency_id = request.business_id,
                        text      = text,
                        file_name = kf.name or kf.id
                    )
                    print(f"   ✅ Ingested: {kf.name}")
                else:
                    print(f"   ⚠️ No text extracted: {kf.name}")
            else:
                print(f"   ❌ Download failed: {kf.name}")
                errors.append(f"Knowledge file download failed: {kf.name}")

        except Exception as e:
            print(f"   ❌ Error: {kf.name} | {str(e)}")
            errors.append(f"Knowledge file error: {kf.name}")

    print(f"✅ Step 4: Knowledge files done")

    # ============================================
    # Step 5 — Agency Store এ Save করো
    # ============================================
    instance_id = f"ai-{request.business_id}"
    AGENCY_STORE[request.business_id] = {
        "business_id"         : request.business_id,
        "business_name"       : request.business_name,
        "vapi_assistant_id"   : assistant_id,
        "vapi_phone_number_id": vapi_phone_number_id,
        "human_agent_phone"   : request.human_agent_phone,
        "twilio_number"       : request.twilio.twilio_number,
        "is_active"           : request.is_active
    }

    print(f"\n✅ Provision Complete | Business: {request.business_id}")

    # Error থাকলে Django কে জানাও
    if errors:
        return {
            "success"    : False,
            "instance_id": None,
            "status"     : "partial_failure",
            "errors"     : errors
        }

    return {
        "success"    : True,
        "instance_id": instance_id,
        "status"     : "provisioned",
        "errors"     : []
    }


# ============================================
# PATCH /agencies/{business_id}/
# কাজ : Config update হলে Django এই endpoint call করে
# ============================================
@router.patch("/{business_id}")
async def update_agency_config(business_id: str, request: PatchRequest):
    """
    কাজ  : Agency র config update করে
    করে  :
    → Voice change → (future)
    → Knowledge file add/remove → Pinecone update
    → Twilio change → Vapi তে update
    """

    print(f"\n🔄 Config Update | Business: {business_id}")

    if business_id not in AGENCY_STORE:
        return {
            "success" : False,
            "is_valid": False,
            "errors"  : [f"Business {business_id} not found"]
        }

    errors = []

    # Knowledge Files Update
    for kf in (request.knowledge_files or []):
        try:
            if kf.action == "remove":
                # Pinecone থেকে remove করো
                await rag_service.delete_file_from_chromadb(
                    agency_id = business_id,
                    file_name = kf.name or kf.id
                )
                print(f"   🗑️ Removed: {kf.name}")

            elif kf.action == "add":
                # Download + Pinecone তে add করো
                async with httpx.AsyncClient() as client:
                    file_response = await client.get(kf.file_url, timeout=60)

                if file_response.status_code == 200:
                    from app.services.file_parser import parse_file_content
                    text = parse_file_content(
                        content  = file_response.content,
                        file_name= kf.name or kf.id,
                        file_type= kf.file_type
                    )
                    if text:
                        await rag_service.ingest_document(
                            agency_id = business_id,
                            text      = text,
                            file_name = kf.name or kf.id
                        )
                        print(f"   ✅ Added: {kf.name}")

        except Exception as e:
            errors.append(f"Knowledge file error: {kf.name} | {str(e)}")

    print(f"✅ Config Update Complete | Business: {business_id}")

    if errors:
        return {
            "success" : False,
            "is_valid": False,
            "errors"  : errors
        }

    return {
        "success" : True,
        "is_valid": True,
        "errors"  : []
    }


# ============================================
# GET /agencies/{business_id}/
# কাজ : Agency র current config দেখায় (debug)
# ============================================
@router.get("/{business_id}")
async def get_agency_info(business_id: str):
    """
    কাজ  : Agency র stored info দেখায়
    """
    if business_id not in AGENCY_STORE:
        raise HTTPException(status_code=404, detail="Business not found")

    return AGENCY_STORE[business_id]


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test/ping")
async def agencies_test():
    return {
        "router"           : "agencies",
        "status"           : "ready",
        "total_provisioned": len(AGENCY_STORE)
    }