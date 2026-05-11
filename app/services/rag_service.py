"""
ফাইলের নাম  : rag_service.py
ফাইলের কাজ  : RAG (Retrieval Augmented Generation) এর সব কাজ করে
               
               INGESTION PIPELINE:
               File text → Chunks → Embeddings → ChromaDB
               
               RETRIEVAL PIPELINE:
               User Query → Embed → Search ChromaDB → Context Return
               
কে use করে  : knowledge_base.py (file upload এ)
               webhooks.py (inbound call এ query করতে)
সংযুক্ত     : config.py (OpenAI Key এর জন্য)
               file_parser.py (text extract এর জন্য)

Chunking    : 500 tokens, 50 overlap
Embedding   : OpenAI text-embedding-3-small
Vector DB   : ChromaDB (Local)
Multi-tenant: প্রতি Agency র আলাদা Collection
"""

import chromadb
import openai
import tiktoken
from app import config

# OpenAI Client Setup
openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

# ChromaDB Client Setup
# কাজ: Local এ ChromaDB চালু করে
# সব data এই folder এ save হবে
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Tokenizer Setup
# কাজ: Text কে tokens এ convert করে
# chunk size measure করতে দরকার
tokenizer = tiktoken.get_encoding("cl100k_base")


# ============================================
# CHUNKING FUNCTION
# কাজ : বড় text কে ছোট ছোট chunks এ ভাগ করে
# কেন : LLM একসাথে পুরো document নিতে পারে না
#        500 tokens এর chunk নিতে পারে
# ============================================
def create_chunks(text: str, chunk_size: int = 500, overlap: int = 50):
    """
    কাজ  : বড় text কে 500 token এর chunks এ ভাগ করে
    নেয়  : text (যেকোনো বড় text)
    দেয়  : chunks list (প্রতিটা chunk 500 token এর)
    
    উদাহরণ:
    Input : "আমি insurance নিতে চাই... [5000 words]"
    Output: [chunk1(500 tokens), chunk2(500 tokens), ...]
    
    Overlap কেন:
    chunk1 এর শেষ 50 token = chunk2 এর শুরু 50 token
    → Context হারায় না
    """

    # Text কে tokens এ convert করো
    tokens = tokenizer.encode(text)
    
    chunks = []
    start = 0
    
    while start < len(tokens):
        # 500 token এর একটা chunk নাও
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        
        # Tokens কে আবার text এ convert করো
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        
        # পরের chunk এর শুরু
        # Overlap এর জন্য 50 token পিছিয়ে শুরু করো
        start = end - overlap
    
    print(f"✂️ RAG: Text chunked | Total chunks: {len(chunks)}")
    return chunks



# ============================================
# EMBEDDING FUNCTION
# কাজ : Text কে Vector (numbers) এ convert করে
# কেন : ChromaDB text বোঝে না, শুধু numbers বোঝে
#        Semantic search এর জন্য vector লাগে
# ============================================
async def create_embedding(text: str):
    """
    কাজ  : একটা text কে vector এ convert করে
    নেয়  : text (chunk বা user query)
    দেয়  : vector (1536 numbers এর list)
    
    উদাহরণ:
    Input : "health insurance premium কত?"
    Output: [0.123, -0.456, 0.789, ...] (1536 numbers)
    
    কেন OpenAI text-embedding-3-small:
    → Cheap (প্রতি 1M token = $0.02)
    → Fast
    → Bengali + English দুইটাই বোঝে
    """

    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        vector = response.data[0].embedding
        print(f"🔢 RAG: Embedding created | Dimensions: {len(vector)}")
        return vector

    except Exception as e:
        print(f"❌ RAG: Embedding failed | Error: {str(e)}")
        return None


# ============================================
# BATCH EMBEDDING FUNCTION  
# কাজ : অনেকগুলো chunks একসাথে embed করে
# কেন : প্রতিটা chunk আলাদা আলাদা embed করলে
#        অনেক API call লাগে, slow হয়
#        Batch এ করলে fast + cheap
# ============================================
async def create_batch_embeddings(chunks: list):
    """
    কাজ  : সব chunks একসাথে embed করে
    নেয়  : chunks list
    দেয়  : vectors list (প্রতিটা chunk এর জন্য একটা vector)
    
    উদাহরণ:
    Input : [chunk1, chunk2, chunk3, ...]
    Output: [vector1, vector2, vector3, ...]
    """

    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=chunks
        )
        vectors = [item.embedding for item in response.data]
        print(f"🔢 RAG: Batch embeddings created | Total: {len(vectors)}")
        return vectors

    except Exception as e:
        print(f"❌ RAG: Batch embedding failed | Error: {str(e)}")
        return None
    


# ============================================
# CHROMADB COLLECTION GET/CREATE
# কাজ : প্রতি Agency র আলাদা Collection বানায়
# কেন : Multi-tenant এ data isolation দরকার
#        Agency A র data Agency B দেখতে পাবে না
# ============================================
def get_agency_collection(agency_id: int):
    """
    কাজ  : Agency র ChromaDB collection নিয়ে আসে
            না থাকলে নতুন বানায়
    নেয়  : agency_id
    দেয়  : ChromaDB collection object
    
    উদাহরণ:
    Agency 1 → collection name: "agency_1_knowledge"
    Agency 2 → collection name: "agency_2_knowledge"
    """

    collection_name = f"agency_{agency_id}_knowledge"

    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"agency_id": str(agency_id)}
    )

    print(f"📚 RAG: Collection ready | Name: {collection_name}")
    return collection


# ============================================
# SAVE TO CHROMADB (INGESTION)
# কাজ : Chunks + Vectors ChromaDB তে save করে
# কেন : পরে search করার জন্য store করতে হয়
# ============================================
async def save_to_chromadb(
    agency_id: int,
    chunks: list,
    vectors: list,
    file_name: str
):
    """
    কাজ  : Chunks এবং তাদের Vectors ChromaDB তে save করে
    নেয়  : agency_id, chunks, vectors, file_name
    দেয়  : True (success) / False (failure)
    কখন : File upload হলে ingestion pipeline এ

    ChromaDB তে যা save হয়:
    → documents : actual chunk text
    → embeddings: chunk এর vector
    → metadatas : chunk এর extra info
    → ids       : প্রতিটা chunk এর unique id
    """

    try:
        collection = get_agency_collection(agency_id)

        # প্রতিটা chunk এর জন্য unique ID বানাও
        ids = [
            f"agency_{agency_id}_{file_name}_chunk_{i}"
            for i in range(len(chunks))
        ]

        # Metadata বানাও
        # কোন file থেকে এসেছে সেটা রাখবো
        metadatas = [
            {
                "agency_id": str(agency_id),
                "file_name": file_name,
                "chunk_index": str(i)
            }
            for i in range(len(chunks))
        ]

        # ChromaDB তে save করো
        collection.add(
            documents=chunks,
            embeddings=vectors,
            metadatas=metadatas,
            ids=ids
        )

        print(f"💾 RAG: Saved to ChromaDB | Agency: {agency_id} | Chunks: {len(chunks)}")
        return True

    except Exception as e:
        print(f"❌ RAG: Save failed | Error: {str(e)}")
        return False


# ============================================
# DELETE FILE FROM CHROMADB
# কাজ : Agency কোনো file delete করলে
#        সেই file এর সব chunks মুছে দেয়
# ============================================
async def delete_file_from_chromadb(agency_id: int, file_name: str):
    """
    কাজ  : একটা file এর সব chunks ChromaDB থেকে delete করে
    নেয়  : agency_id, file_name
    দেয়  : True (success) / False (failure)
    কখন : Agency file delete করলে
    """

    try:
        collection = get_agency_collection(agency_id)

        # এই file এর সব chunks খুঁজে delete করো
        collection.delete(
            where={"file_name": file_name}
        )

        print(f"🗑️ RAG: File deleted | Agency: {agency_id} | File: {file_name}")
        return True

    except Exception as e:
        print(f"❌ RAG: Delete failed | Error: {str(e)}")
        return False
    



# ============================================
# MAIN INGESTION PIPELINE
# কাজ : File এর text নিয়ে পুরো ingestion করে
#        Chunk → Embed → Save একসাথে
# কেন : file_parser.py text দেবে
#        এই function বাকি সব করবে
# কে call করে : knowledge_base.py (file upload এ)
# ============================================
async def ingest_document(
    agency_id: int,
    text: str,
    file_name: str
):
    """
    কাজ  : Document এর text নিয়ে পুরো ingestion pipeline চালায়
    নেয়  : agency_id, text (file থেকে extracted), file_name
    দেয়  : True (success) / False (failure)
    কখন : Agency file upload করলে

    Pipeline:
    text → chunks → embeddings → ChromaDB save
    """

    print(f"\n🚀 RAG: Ingestion started | Agency: {agency_id} | File: {file_name}")
    print(f"   Text length: {len(text)} characters")

    # Step 1 — Text কে Chunks এ ভাগ করো
    print(f"\n📌 Step 1: Chunking...")
    chunks = create_chunks(text)
    if not chunks:
        print(f"❌ RAG: No chunks created")
        return False
    print(f"   ✅ {len(chunks)} chunks created")

    # Step 2 — সব Chunks Embed করো
    print(f"\n📌 Step 2: Creating embeddings...")
    vectors = await create_batch_embeddings(chunks)
    if not vectors:
        print(f"❌ RAG: Embeddings failed")
        return False
    print(f"   ✅ {len(vectors)} embeddings created")

    # Step 3 — ChromaDB তে Save করো
    print(f"\n📌 Step 3: Saving to ChromaDB...")
    saved = await save_to_chromadb(
        agency_id=agency_id,
        chunks=chunks,
        vectors=vectors,
        file_name=file_name
    )
    if not saved:
        print(f"❌ RAG: Save failed")
        return False
    print(f"   ✅ Saved to ChromaDB")

    print(f"\n✅ RAG: Ingestion complete | Agency: {agency_id} | File: {file_name}")
    print(f"   Chunks: {len(chunks)} | Embeddings: {len(vectors)}\n")
    return True


# ============================================
# GET COLLECTION STATS
# কাজ : Agency র knowledge base এর info দেয়
# কেন : Dashboard এ দেখাবো কতটা data আছে
# ============================================
def get_collection_stats(agency_id: int):
    """
    কাজ  : Agency র ChromaDB collection এর stats দেয়
    নেয়  : agency_id
    দেয়  : stats (total chunks, files list)
    কখন : Dashboard এ knowledge base info দেখাতে
    """

    try:
        collection = get_agency_collection(agency_id)
        total_chunks = collection.count()

        # কোন কোন file আছে সেটা বের করো
        if total_chunks > 0:
            results = collection.get(include=["metadatas"])
            files = list(set([
                m.get("file_name", "unknown")
                for m in results.get("metadatas", [])
            ]))
        else:
            files = []

        stats = {
            "agency_id": agency_id,
            "total_chunks": total_chunks,
            "total_files": len(files),
            "files": files
        }

        print(f"📊 RAG: Stats | Agency: {agency_id} | Chunks: {total_chunks} | Files: {len(files)}")
        return stats

    except Exception as e:
        print(f"❌ RAG: Stats failed | Error: {str(e)}")
        return {
            "agency_id": agency_id,
            "total_chunks": 0,
            "total_files": 0,
            "files": []
        }
    

# ============================================
# SEARCH CHROMADB (RETRIEVAL)
# কাজ : Customer এর প্রশ্নের সাথে মিলিয়ে
#        ChromaDB থেকে relevant chunks খুঁজে আনে
# ============================================
async def search_knowledge_base(
    agency_id: int,
    query: str,
    top_k: int = 3
):
    """
    কাজ  : Customer এর query দিয়ে ChromaDB তে search করে
    নেয়  : agency_id, query, top_k
    দেয়  : relevant chunks list
    কখন : Inbound call এ customer প্রশ্ন করলে
    """

    try:
        collection = get_agency_collection(agency_id)

        if collection.count() == 0:
            print(f"⚠️ RAG: No data | Agency: {agency_id}")
            return []

        # Query embed করো
        query_vector = await create_embedding(query)
        if not query_vector:
            return []

        # ChromaDB তে search করো
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "distances"]
        )

        chunks = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        print(f"🔍 RAG: Search done | Query: '{query[:50]}' | Found: {len(chunks)}")

        for i, (chunk, dist) in enumerate(zip(chunks, distances)):
            print(f"   Chunk {i+1}: score={round(1-dist, 2)} | {chunk[:80]}...")

        return chunks

    except Exception as e:
        print(f"❌ RAG: Search failed | Error: {str(e)}")
        return []



# ============================================
# BUILD CONTEXT FOR LLM
# কাজ : Search results কে LLM এর জন্য
#        একটা clean context এ convert করে
# কে call করে : webhooks.py (inbound call এ)
# ============================================
async def build_context(agency_id: int, query: str):
    """
    কাজ  : Search করে relevant chunks নিয়ে
            LLM এর জন্য clean context বানায়
    নেয়  : agency_id, query
    দেয়  : formatted context string
    কখন : Inbound call এ Vapi System Prompt এ inject করতে
    """

    chunks = await search_knowledge_base(agency_id, query)

    if not chunks:
        return ""

    context = "=== Insurance Knowledge Base ===\n\n"
    for i, chunk in enumerate(chunks, 1):
        context += f"[Info {i}]\n{chunk}\n\n"

    print(f"📝 RAG: Context built | Agency: {agency_id} | Length: {len(context)} chars")
    return context