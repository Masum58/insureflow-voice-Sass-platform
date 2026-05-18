"""
ফাইলের নাম  : rag_service.py
ফাইলের কাজ  : RAG Pipeline সব কাজ করে
               
               INGESTION:
               File text → Chunks → Embeddings → Pinecone
               
               RETRIEVAL:
               Query → Embed → Pinecone Search → Context
               
কে use করে  : knowledge_base.py, webhooks.py
সংযুক্ত     : config.py (OpenAI + Pinecone Keys)
               file_parser.py (text extract)

Chunking    : 500 tokens, 50 overlap
Embedding   : OpenAI text-embedding-3-small
Vector DB   : Pinecone (Cloud)
Multi-tenant: প্রতি Agency র আলাদা Namespace
"""

import openai
import tiktoken
from pinecone import Pinecone, ServerlessSpec
from app import config


# ============================================
# CLIENT SETUP
# ============================================
openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
tokenizer     = tiktoken.get_encoding("cl100k_base")

# Pinecone Setup
pc = Pinecone(api_key=config.PINECONE_API_KEY)


# ============================================
# PINECONE INDEX SETUP
# কাজ : Index না থাকলে বানায়, থাকলে নিয়ে আসে
# কখন: Server start হলে একবার চলে
# ============================================
def get_pinecone_index():
    """
    কাজ  : Pinecone Index নিয়ে আসে
            না থাকলে নতুন বানায়
    দেয়  : Pinecone Index object
    """
    index_name = config.PINECONE_INDEX

    # Index আছে কিনা check করো
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing_indexes:
        print(f"📦 Pinecone: Creating index '{index_name}'...")

        pc.create_index(
            name     = index_name,
            dimension= 1536,        # OpenAI text-embedding-3-small
            metric   = "cosine",
            spec     = ServerlessSpec(
                cloud = "aws",
                region= "us-east-1"
            )
        )
        print(f"✅ Pinecone: Index created | Name: {index_name}")
    else:
        print(f"✅ Pinecone: Index found | Name: {index_name}")

    return pc.Index(index_name)


# Index নিয়ে আসো
pinecone_index = get_pinecone_index()


# ============================================
# NAMESPACE HELPER
# কাজ : Agency র namespace বানায়
# Multi-tenant: প্রতি Agency আলাদা namespace
# ============================================
def get_namespace(agency_id: int) -> str:
    """
    কাজ  : Agency র Pinecone namespace return করে
    নেয়  : agency_id
    দেয়  : namespace string

    উদাহরণ:
    Agency 1 → "agency_1"
    Agency 2 → "agency_2"
    """
    return f"agency_{agency_id}"


# ============================================
# CHUNKING FUNCTION
# কাজ : বড় text কে ছোট chunks এ ভাগ করে
# ============================================
def create_chunks(text: str, chunk_size: int = 500, overlap: int = 50):
    """
    কাজ  : Text কে 500 token এর chunks এ ভাগ করে
    নেয়  : text
    দেয়  : chunks list
    """
    tokens = tokenizer.encode(text)
    chunks = []
    start  = 0

    while start < len(tokens):
        end          = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text   = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end - overlap

    print(f"✂️ RAG: Chunked | Total: {len(chunks)}")
    return chunks


# ============================================
# EMBEDDING FUNCTIONS
# ============================================
async def create_embedding(text: str):
    """
    কাজ  : একটা text কে vector এ convert করে
    নেয়  : text
    দেয়  : vector (1536 numbers)
    """
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ RAG: Embedding failed | {str(e)}")
        return None


async def create_batch_embeddings(chunks: list):
    """
    কাজ  : সব chunks একসাথে embed করে
    নেয়  : chunks list
    দেয়  : vectors list
    """
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=chunks
        )
        vectors = [item.embedding for item in response.data]
        print(f"🔢 RAG: Batch embeddings | Total: {len(vectors)}")
        return vectors
    except Exception as e:
        print(f"❌ RAG: Batch embedding failed | {str(e)}")
        return None


# ============================================
# SAVE TO PINECONE (INGESTION)
# কাজ : Chunks + Vectors Pinecone তে save করে
# ============================================
async def save_to_pinecone(
    agency_id: int,
    chunks   : list,
    vectors  : list,
    file_name: str
):
    """
    কাজ  : Chunks + Vectors Pinecone তে save করে
    নেয়  : agency_id, chunks, vectors, file_name
    দেয়  : True/False
    """
    try:
        namespace = get_namespace(agency_id)

        # Pinecone format এ vectors বানাও
        vectors_to_upsert = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            vectors_to_upsert.append({
                "id"    : f"agency_{agency_id}_{file_name}_chunk_{i}",
                "values": vector,
                "metadata": {
                    "agency_id" : str(agency_id),
                    "file_name" : file_name,
                    "chunk_index": str(i),
                    "text"      : chunk[:1000]  # Metadata এ text রাখো
                }
            })

        # Pinecone তে upsert করো (batch এ)
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            pinecone_index.upsert(
                vectors  = batch,
                namespace= namespace
            )

        print(f"💾 RAG: Saved to Pinecone | Agency: {agency_id} | Chunks: {len(chunks)}")
        return True

    except Exception as e:
        print(f"❌ RAG: Pinecone save failed | {str(e)}")
        return False


# ============================================
# DELETE FILE FROM PINECONE
# কাজ : File delete হলে Pinecone থেকেও মুছে দেয়
# ============================================
async def delete_file_from_chromadb(agency_id: int, file_name: str):
    """
    কাজ  : File এর সব chunks Pinecone থেকে delete করে
    নেয়  : agency_id, file_name
    দেয়  : True/False
    """
    try:
        namespace = get_namespace(agency_id)

        # এই file এর সব vector ID বের করো
        prefix = f"agency_{agency_id}_{file_name}_chunk_"

        # Pinecone তে delete করো
        pinecone_index.delete(
            namespace= namespace,
            filter   = {"file_name": {"$eq": file_name}}
        )

        print(f"🗑️ RAG: Deleted | Agency: {agency_id} | File: {file_name}")
        return True

    except Exception as e:
        print(f"❌ RAG: Delete failed | {str(e)}")
        return False


# ============================================
# MAIN INGESTION PIPELINE
# কাজ : পুরো ingestion একসাথে করে
# ============================================
async def ingest_document(agency_id: int, text: str, file_name: str):
    """
    কাজ  : Document text নিয়ে পুরো pipeline চালায়
    নেয়  : agency_id, text, file_name
    দেয়  : True/False
    Pipeline: text → chunks → embeddings → Pinecone
    """

    print(f"\n🚀 RAG: Ingestion | Agency: {agency_id} | File: {file_name}")

    # Step 1 — Chunking
    chunks = create_chunks(text)
    if not chunks:
        return False
    print(f"   ✅ {len(chunks)} chunks")

    # Step 2 — Embedding
    vectors = await create_batch_embeddings(chunks)
    if not vectors:
        return False
    print(f"   ✅ {len(vectors)} embeddings")

    # Step 3 — Pinecone Save
    saved = await save_to_pinecone(agency_id, chunks, vectors, file_name)
    if not saved:
        return False
    print(f"   ✅ Saved to Pinecone")

    print(f"✅ RAG: Complete | {len(chunks)} chunks\n")
    return True


# ============================================
# GET COLLECTION STATS
# কাজ : Agency র knowledge base stats দেয়
# ============================================
def get_collection_stats(agency_id: int):
    """
    কাজ  : Pinecone namespace এর stats দেয়
    নেয়  : agency_id
    দেয়  : stats dict
    """
    try:
        namespace = get_namespace(agency_id)
        stats     = pinecone_index.describe_index_stats()
        ns_stats  = stats.namespaces.get(namespace, {})
        total     = ns_stats.get("vector_count", 0)

        print(f"📊 RAG: Stats | Agency: {agency_id} | Vectors: {total}")
        return {
            "agency_id"   : agency_id,
            "total_chunks": total,
            "namespace"   : namespace
        }

    except Exception as e:
        print(f"❌ RAG: Stats failed | {str(e)}")
        return {"agency_id": agency_id, "total_chunks": 0}


# ============================================
# SEARCH PINECONE (RETRIEVAL)
# কাজ : Query দিয়ে Pinecone তে search করে
# ============================================
async def search_knowledge_base(
    agency_id: int,
    query    : str,
    top_k    : int = 3
):
    """
    কাজ  : Query দিয়ে Pinecone তে semantic search করে
    নেয়  : agency_id, query, top_k
    দেয়  : relevant chunks list
    """
    try:
        namespace    = get_namespace(agency_id)
        query_vector = await create_embedding(query)

        if not query_vector:
            return []

        # Pinecone তে search করো
        results = pinecone_index.query(
            vector   = query_vector,
            top_k    = top_k,
            namespace= namespace,
            include_metadata=True
        )

        # Chunks বের করো
        chunks = []
        for match in results.matches:
            text = match.metadata.get("text", "")
            score= round(match.score, 2)
            chunks.append(text)
            print(f"   Match: score={score} | {text[:80]}...")

        print(f"🔍 RAG: Search | Query: '{query[:50]}' | Found: {len(chunks)}")
        return chunks

    except Exception as e:
        print(f"❌ RAG: Search failed | {str(e)}")
        return []


# ============================================
# BUILD CONTEXT FOR LLM
# কাজ : Search results কে LLM এর জন্য format করে
# ============================================
async def build_context(agency_id: int, query: str):
    """
    কাজ  : Relevant chunks নিয়ে LLM এর জন্য context বানায়
    নেয়  : agency_id, query
    দেয়  : formatted context string
    """
    chunks = await search_knowledge_base(agency_id, query)

    if not chunks:
        return ""

    context = "=== Insurance Knowledge Base ===\n\n"
    for i, chunk in enumerate(chunks, 1):
        context += f"[Info {i}]\n{chunk}\n\n"

    print(f"📝 RAG: Context built | Length: {len(context)} chars")
    return context