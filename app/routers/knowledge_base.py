"""
ফাইলের নাম  : knowledge_base.py
ফাইলের কাজ  : Agency র knowledge base manage করে
               
               1. File upload (PDF/CSV/XML/TXT)
               2. Upload হলে → parse → ChromaDB or Pinecone save
               3. Files list দেখা
               4. File delete করা
               
কে call করে : Frontend Dashboard (Agency Owner)
সংযুক্ত     : file_parser.py (text extract)
               rag_service.py (ChromaDB save)
               db_service.py (file info save)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import file_parser, rag_service, db_service

router = APIRouter()


# ============================================
# UPLOAD FILE
# কাজ : Agency র file upload করে
#        Parse করে ChromaDB তে save করে
# URL : POST /knowledge-base/upload
# কে call করে : Frontend Dashboard
# ============================================
@router.post("/upload")
async def upload_file(
    agency_id: int,
    file: UploadFile = File(...)
):
    """
    কাজ  : File upload করে knowledge base এ add করে
    নেয়  : agency_id, file (PDF/CSV/XML/TXT)
    দেয়  : success/failure message
    করে  : 
    1. File read করে
    2. File type check করে
    3. Text extract করে
    4. ChromaDB তে save করে
    5. DB তে file info save করে
    """

    # ============================================
    # Step 1 — File Type Check করো
    # ============================================
    file_name = file.filename
    file_type = file_parser.get_file_type(file_name)

    print(f"\n📤 Upload: Starting | Agency: {agency_id} | File: {file_name}")

    # Supported types check
    supported_types = ["pdf", "csv", "xml", "txt"]
    if file_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"❌ Unsupported file type: {file_type}. Supported: {supported_types}"
        )

    # ============================================
    # Step 2 — File Content Read করো
    # ============================================
    try:
        file_content = await file.read()
        file_size = len(file_content)
        print(f"📦 Upload: File read | Size: {file_size} bytes")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"❌ File read failed: {str(e)}"
        )

    # ============================================
    # Step 3 — Text Extract করো
    # ============================================
    print(f"🔍 Upload: Extracting text...")
    extracted_text = await file_parser.parse_file(
        file_content=file_content,
        file_name=file_name,
        file_type=file_type
    )

    if not extracted_text:
        raise HTTPException(
            status_code=422,
            detail=f"❌ No text could be extracted from {file_name}"
        )

    print(f"✅ Upload: Text extracted | Characters: {len(extracted_text)}")

    # ============================================
    # Step 4 — ChromaDB তে Save করো
    # ============================================
    print(f"💾 Upload: Saving to ChromaDB...")
    ingested = await rag_service.ingest_document(
        agency_id=agency_id,
        text=extracted_text,
        file_name=file_name
    )

    if not ingested:
        raise HTTPException(
            status_code=500,
            detail=f"❌ Failed to save to knowledge base"
        )

    # ============================================
    # Step 5 — Stats নাও
    # ============================================
    stats = rag_service.get_collection_stats(agency_id=agency_id)

    print(f"✅ Upload: Complete | Agency: {agency_id} | File: {file_name}")

    return {
        "status": "success ✅",
        "message": f"{file_name} successfully added to knowledge base",
        "file_info": {
            "name": file_name,
            "type": file_type,
            "size_bytes": file_size,
            "characters_extracted": len(extracted_text)
        },
        "knowledge_base_stats": stats
    }


# ============================================
# GET FILES LIST
# কাজ : Agency র সব uploaded files দেখায়
# URL : GET /knowledge-base/files
# কে call করে : Frontend Dashboard
# ============================================
@router.get("/files")
async def get_files(agency_id: int):
    """
    কাজ  : Agency র knowledge base এ কী কী file আছে দেখায়
    নেয়  : agency_id
    দেয়  : files list with stats
    """

    print(f"📋 Files: Getting list | Agency: {agency_id}")

    stats = rag_service.get_collection_stats(agency_id=agency_id)

    return {
        "agency_id": agency_id,
        "total_files": stats.get("total_files", 0),
        "total_chunks": stats.get("total_chunks", 0),
        "files": stats.get("files", [])
    }


# ============================================
# DELETE FILE
# কাজ : Agency র একটা file delete করে
# URL : DELETE /knowledge-base/files/{file_name}
# কে call করে : Frontend Dashboard
# ============================================
@router.delete("/files/{file_name}")
async def delete_file(agency_id: int, file_name: str):
    """
    কাজ  : Knowledge base থেকে একটা file delete করে
    নেয়  : agency_id, file_name
    দেয়  : success/failure
    করে  : ChromaDB থেকে সেই file এর সব chunks delete করে
    """

    print(f"🗑️ Delete: Starting | Agency: {agency_id} | File: {file_name}")

    deleted = await rag_service.delete_file_from_chromadb(
        agency_id=agency_id,
        file_name=file_name
    )

    if not deleted:
        raise HTTPException(
            status_code=500,
            detail=f"❌ Failed to delete {file_name}"
        )

    stats = rag_service.get_collection_stats(agency_id=agency_id)

    return {
        "status": "success ✅",
        "message": f"{file_name} deleted from knowledge base",
        "remaining_stats": stats
    }


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def knowledge_base_test():
    """
    কাজ : Knowledge base router কাজ করছে কিনা check করে
    """
    return {
        "router": "knowledge_base",
        "status": "ready",
        "endpoints": [
            "POST /knowledge-base/upload",
            "GET  /knowledge-base/files",
            "DELETE /knowledge-base/files/{file_name}"
        ]
    }