"""
File Name : auth.py

What this file does:
- Handles login and authentication related APIs
- Manages user access and security tokens

Who calls this file:
- Frontend dashboard
- Admin panel
- External apps using authentication

Connected with:
- config.py
"""

"""
ফাইলের নাম  : auth.py
ফাইলের কাজ  : Login এবং Token management
               এখন db_service test endpoint আছে
কে call করে : Frontend Dashboard
সংযুক্ত     : db_service.py
"""

from fastapi import APIRouter
from app.services import db_service
from app import config

router = APIRouter()


# ============================================
# DB SERVICE TEST
# কাজ : db_service এর সব functions test করে
# URL : GET /auth/test-db
# ============================================
@router.get("/test-db")
async def test_db_service():
    """
    কাজ  : db_service এর সব functions একসাথে test করে
    দেয়  : সব functions এর result
    """

    # Agency test
    agency = await db_service.get_agency(1)
    

    # Lead test
    leads = await db_service.get_queued_leads(1)
    lead = await db_service.get_lead(1)

    # Call test
    saved_call = await db_service.save_call({
        "call_id": "test_call_123",
        "lead_id": 1,
        "agency_id": 1,
        "status": "in_progress"
    })

    updated_call = await db_service.update_call("test_call_123", {
        "status": "ended",
        "intent": "interested",
        "duration": 120
    })

    # Meeting test
    saved_meeting = await db_service.save_meeting({
        "call_id": "test_call_123",
        "lead_id": 1,
        "agency_id": 1,
        "meeting_link": "https://calendly.com/test",
        "scheduled_at": "2025-05-10T14:00:00Z"
    })

    return {
        "status": "all tests passed ✅",
        "results": {
            "agency": agency,
            "leads_count": len(leads),
            "lead": lead,
            "saved_call": saved_call,
            "updated_call": updated_call,
            "saved_meeting": saved_meeting
        }
    }


@router.get("/test-ghl")
async def test_ghl_service():
    """
    কাজ : ghl_service এর সব functions test করে
    """
    from app.services import ghl_service

    status  = await ghl_service.update_contact_status(
        "test_123", "interested", 1
    )
    note    = await ghl_service.add_call_note(
        "test_123", "Customer interested in health insurance", 142, "interested"
    )
    contact = await ghl_service.create_contact(
        "Test User", "+8801711111111", 1
    )
    meeting = await ghl_service.sync_meeting(
        "test_123", "https://calendly.com/test", "2025-05-10T14:00:00Z", "Test User"
    )

    return {
        "status": "tests completed ✅",
        "ghl_configured": ghl_service.is_ghl_configured(),
        "results": {
            "contact_status_updated": status,
            "note_added": note,
            "contact_created": contact,
            "meeting_synced": meeting
        }
    }



@router.get("/test-rag")
async def test_rag_service():
    """
    কাজ : rag_service এর পুরো pipeline test করে
          Ingestion + Retrieval দুইটাই test হবে
    """
    from app.services import rag_service

    # Test Text (fake insurance data)
    test_text = """
    ABC Insurance Health Plan Information
    
    Premium Details:
    Our health insurance monthly premium starts from 500 taka.
    Family plan premium is 1200 taka per month.
    Individual plan premium is 500 taka per month.
    Senior citizen plan premium is 800 taka per month.
    
    Payment Methods:
    You can pay premium via bKash, Nagad, Rocket.
    Bank transfer is also accepted.
    Cash payment available at our offices.
    
    Coverage Details:
    Our health insurance covers hospitalization up to 5 lakh taka.
    Outpatient coverage up to 50,000 taka per year.
    Maternity coverage included in family plan.
    Pre-existing conditions covered after 2 years.
    
    Claim Process:
    To file a claim, call our helpline 16xxx.
    Submit claim form within 30 days of discharge.
    Claim settlement within 15 working days.
    Direct cashless treatment available at 500+ hospitals.
    """

    # Step 1 — Ingestion Test
    print("\n🧪 Testing Ingestion Pipeline...")
    ingested = await rag_service.ingest_document(
        agency_id=99,
        text=test_text,
        file_name="test_health_insurance.txt"
    )

    # Step 2 — Stats Test
    stats = rag_service.get_collection_stats(agency_id=99)

    # Step 3 — Retrieval Test
    print("\n🧪 Testing Retrieval Pipeline...")
    context = await rag_service.build_context(
        agency_id=99,
        query="health insurance premium কত?"
    )

    # Step 4 — Search Test
    chunks = await rag_service.search_knowledge_base(
        agency_id=99,
        query="claim process কীভাবে করবো?"
    )

    return {
        "status": "all tests passed ✅",
        "ingestion": {
            "success": ingested,
            "stats": stats
        },
        "retrieval": {
            "query": "health insurance premium কত?",
            "context_length": len(context),
            "context_preview": context[:200] + "..."
        },
        "search": {
            "query": "claim process কীভাবে করবো?",
            "chunks_found": len(chunks),
            "first_chunk": chunks[0][:150] + "..." if chunks else "none"
        }
    }

# পুরানো check-chromadb এর জায়গায়
@router.get("/check-pinecone")
async def check_pinecone():
    """
    কাজ : Pinecone এ কী data আছে দেখায়
    """
    from app.services import rag_service

    stats = rag_service.pinecone_index.describe_index_stats()

    return {
        "index_name"      : config.PINECONE_INDEX,
        "total_vectors"   : stats.total_vector_count,
        "namespaces"      : dict(stats.namespaces),
        "dimension"       : stats.dimension
    }



@router.get("/view-chromadb")
async def view_chromadb_data(agency_id: int = 99):
    """
    কাজ : ChromaDB তে save হওয়া actual data দেখায়
    """
    import chromadb

    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection_name = f"agency_{agency_id}_knowledge"

    try:
        collection = chroma_client.get_collection(collection_name)
    except:
        return {"error": f"Collection '{collection_name}' নেই"}

    total = collection.count()
    all_data = collection.get(
        include=["documents", "metadatas", "embeddings"]
    )

    embeddings_preview = []
    # ✅ Fix: is not None দিয়ে check করো
    if all_data.get("embeddings") is not None:
        for emb in all_data["embeddings"]:
            embeddings_preview.append({
                "first_5_numbers": list(emb[:5]),
                "total_dimensions": len(emb)
            })

    return {
        "collection_name": collection_name,
        "total_chunks": total,
        "data": [
            {
                "chunk_number": i + 1,
                "id": all_data["ids"][i],
                "text": all_data["documents"][i],
                "metadata": all_data["metadatas"][i],
                "embedding_preview": embeddings_preview[i] if embeddings_preview else None
            }
            for i in range(total)
        ]
    }

@router.get("/check-redis")
async def check_redis():
    """
    কাজ : Redis এ save হওয়া data দেখায়
    """
    import redis
    import json

    r = redis.from_url("redis://localhost:6379")

    # সব campaign keys
    keys = r.keys("campaign:*")
    result = {}

    for key in keys:
        key_str = key.decode("utf-8")
        key_type = r.type(key).decode("utf-8")

        if key_type == "list":
            items = r.lrange(key, 0, -1)
            result[key_str] = {
                "type": "queue",
                "total": len(items),
                "items": [json.loads(i) for i in items[:3]]
            }
        elif key_type == "string":
            data = r.get(key)
            result[key_str] = {
                "type": "status",
                "data": json.loads(data)
            }

    return {
        "total_keys": len(keys),
        "redis_data": result
    }

@router.get("/test")
async def auth_test():
    return {"router": "auth", "status": "ready"}