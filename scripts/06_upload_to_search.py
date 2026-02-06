"""
06 - Upload PDF Files to Azure AI Search
Uploads PDF files from the data folder to Azure AI Search with page-aware chunking.

Usage:
    python 06_upload_to_search.py

Prerequisites:
    - Run 01_generate_sample_data.py (creates PDF files in data folder)
    - Azure AI Search endpoint configured via azd or .env
    - Embedding model deployed in Azure AI Foundry

The script will:
1. Create a search index with vector search and semantic configuration
2. Extract text from PDF pages
3. Chunk text by sentences (respecting boundaries)
4. Generate embeddings using Azure OpenAI
5. Upload documents to the search index
"""

import os
import sys
import json
import re
from pathlib import Path

# Load environment from azd + project .env
from load_env import load_all_env, get_required_env, get_data_folder, print_env_status
load_all_env()

from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from pypdf import PdfReader

# ============================================================================
# Configuration
# ============================================================================

# Azure services - from azd environment
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT") or os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").split("/api/projects")[0]
AZURE_AI_SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

# Project settings - from .env
SOLUTION_NAME = os.getenv("SOLUTION_NAME") or os.getenv("SOLUTION_PREFIX") or os.getenv("AZURE_ENV_NAME", "demo")

# Use AZURE_AI_SEARCH_INDEX from azd env, fallback to generated name
INDEX_NAME = os.getenv("AZURE_AI_SEARCH_INDEX") or f"{SOLUTION_NAME}-documents"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

if not AZURE_AI_SEARCH_ENDPOINT:
    print("ERROR: AZURE_AI_SEARCH_ENDPOINT not set in .env")
    sys.exit(1)

# Get data folder with proper path resolution
try:
    data_dir = Path(get_data_folder())
except ValueError:
    print("ERROR: DATA_FOLDER not set in .env")
    print("       Run 01_generate_data.py first")
    sys.exit(1)

if not data_dir.exists():
    print(f"ERROR: Data folder not found: {data_dir}")
    sys.exit(1)

# Set up paths for new folder structure (config/, tables/, documents/)
config_dir = data_dir / "config"
docs_dir = data_dir / "documents"

# Fallback to old structure if config dir doesn't exist
if not config_dir.exists():
    config_dir = data_dir
if not docs_dir.exists():
    docs_dir = data_dir  # Fallback to root data folder

print(f"\n{'='*60}")
print("Upload PDF Files to Azure AI Search")
print(f"{'='*60}")
print(f"Search Endpoint: {AZURE_AI_SEARCH_ENDPOINT}")
print(f"AI Endpoint: {AZURE_AI_ENDPOINT}")
print(f"Embedding Model: {EMBEDDING_MODEL}")
print(f"Index Name: {INDEX_NAME}")
print(f"Data Folder: {data_dir}")

# ============================================================================
# Azure OpenAI Client
# ============================================================================

def get_openai_client():
    """Create Azure OpenAI client using AI endpoint."""
    if not AZURE_AI_ENDPOINT:
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT not set")
    
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    
    return AzureOpenAI(
        azure_endpoint=AZURE_AI_ENDPOINT,
        api_key=token.token,
        api_version="2024-10-21",
    )

# ============================================================================
# Azure Search Clients
# ============================================================================

def get_search_clients():
    """Create Azure Search clients."""
    credential = DefaultAzureCredential()
    index_client = SearchIndexClient(AZURE_AI_SEARCH_ENDPOINT, credential)
    search_client = SearchClient(AZURE_AI_SEARCH_ENDPOINT, INDEX_NAME, credential)
    
    return index_client, search_client

# ============================================================================
# Create Search Index
# ============================================================================

def create_index(index_client: SearchIndexClient):
    """Create or update the search index with integrated vectorizer."""
    
    # Embedding dimensions by model
    EMBEDDING_DIMENSIONS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }
    dimensions = EMBEDDING_DIMENSIONS.get(EMBEDDING_MODEL, 1536)
    
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="page_number", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.Int32, sortable=True),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name="default-profile"
        ),
    ]
    
    # Integrated vectorizer for query-time embedding
    vectorizer = AzureOpenAIVectorizer(
        vectorizer_name="openai-vectorizer",
        parameters=AzureOpenAIVectorizerParameters(
            resource_url=AZURE_AI_ENDPOINT,
            deployment_name=EMBEDDING_MODEL,
            model_name=EMBEDDING_MODEL,
        )
    )
    
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-algorithm")],
        profiles=[VectorSearchProfile(
            name="default-profile",
            algorithm_configuration_name="default-algorithm",
            vectorizer_name="openai-vectorizer"
        )],
        vectorizers=[vectorizer]
    )
    
    # Semantic configuration for hybrid search
    semantic_config = SemanticConfiguration(
        name="default-semantic",
        prioritized_fields=SemanticPrioritizedFields(
            content_fields=[SemanticField(field_name="content")],
            title_field=SemanticField(field_name="title"),
        )
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])
    
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )
    
    index_client.create_or_update_index(index)
    print(f"[OK] Index '{INDEX_NAME}' ready with integrated vectorizer")

# ============================================================================
# PDF Processing
# ============================================================================

def extract_pages_from_pdf(filepath: Path) -> list[tuple[int, str]]:
    """Extract text content from each page of a PDF file.
    
    Returns list of (page_number, text) tuples (1-indexed page numbers).
    """
    reader = PdfReader(filepath)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append((i + 1, text.strip()))
    return pages

# ============================================================================
# Text Chunking
# ============================================================================

def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving sentence boundaries."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_text_by_sentences(text: str, max_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks that respect sentence boundaries.
    
    Chunks will not exceed max_size and will not cut mid-sentence.
    Overlap is applied by including trailing sentences from previous chunk.
    """
    sentences = split_into_sentences(text)
    
    if not sentences:
        return [text] if text.strip() else []
    
    chunks = []
    current_chunk = []
    current_length = 0
    overlap_sentences = []
    
    for sentence in sentences:
        sentence_len = len(sentence)
        
        # If single sentence exceeds max_size, include it anyway (don't break mid-sentence)
        if sentence_len > max_size:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                overlap_sentences = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[:]
            
            chunks.append(sentence)
            current_chunk = []
            current_length = 0
            overlap_sentences = []
            continue
        
        # Check if adding this sentence would exceed max_size
        potential_length = current_length + sentence_len + (1 if current_chunk else 0)
        
        if potential_length > max_size and current_chunk:
            # Save current chunk
            chunks.append(' '.join(current_chunk))
            
            # Start new chunk with overlap from previous
            overlap_text_len = sum(len(s) for s in overlap_sentences) + len(overlap_sentences)
            if overlap_text_len < overlap and overlap_sentences:
                current_chunk = overlap_sentences[:]
                current_length = overlap_text_len
            else:
                current_chunk = []
                current_length = 0
        
        # Add sentence to current chunk
        current_chunk.append(sentence)
        current_length += sentence_len + (1 if len(current_chunk) > 1 else 0)
        
        # Track sentences for potential overlap
        overlap_sentences = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[:]
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

# ============================================================================
# Embedding Generation
# ============================================================================

def get_embedding(client: AzureOpenAI, text: str) -> list[float]:
    """Generate embedding for text using OpenAI client."""
    response = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return response.data[0].embedding

# ============================================================================
# Main
# ============================================================================

def main():
    # Find PDF files in documents subfolder
    pdf_files = list(docs_dir.glob("*.pdf"))
    if not pdf_files:
        print("\nNo PDF files found in data folder.")
        print(f"Looked in: {docs_dir}")
        print("Run 01_generate_sample_data.py to generate sample PDFs.")
        return
    
    print(f"\nFound {len(pdf_files)} PDF file(s)")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    # Initialize clients
    print("\nInitializing clients...")
    openai_client = get_openai_client()
    print("[OK] OpenAI client initialized")
    
    index_client, search_client = get_search_clients()
    print("[OK] Search clients initialized")
    
    # Create index
    print("\nCreating search index...")
    create_index(index_client)
    
    # Process each PDF
    documents = []
    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")
        
        pages = extract_pages_from_pdf(pdf_path)
        print(f"  Extracted {len(pages)} pages")
        
        for page_num, page_text in pages:
            chunks = chunk_text_by_sentences(page_text)
            
            for chunk_idx, chunk in enumerate(chunks):
                # ID format: filename_pagenumber_chunknumber
                doc_id = f"{pdf_path.stem}_p{page_num}_c{chunk_idx}"
                
                print(f"  Generating embedding for {doc_id}...", end=" ", flush=True)
                embedding = get_embedding(openai_client, chunk)
                print("[OK]")
                
                doc = {
                    "id": doc_id,
                    "content": chunk,
                    "title": pdf_path.stem.replace("_", " ").title(),
                    "source": pdf_path.name,
                    "page_number": page_num,
                    "chunk_id": chunk_idx,
                    "embedding": embedding
                }
                documents.append(doc)
    
    # Upload to search
    print(f"\nUploading {len(documents)} chunks to search index...")
    result = search_client.upload_documents(documents)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"[OK] Uploaded {succeeded}/{len(documents)} documents")
    
    # Save index info
    search_ids_path = config_dir / "search_ids.json"
    search_info = {
        "index_name": INDEX_NAME,
        "document_count": len(documents),
        "pdf_files": [p.name for p in pdf_files]
    }
    with open(search_ids_path, "w") as f:
        json.dump(search_info, f, indent=2)
    print(f"[OK] Search info saved to: {search_ids_path}")
    
    print(f"\n{'='*60}")
    print("Upload Complete!")
    print(f"{'='*60}")
    print(f"Index: {INDEX_NAME}")
    print(f"Documents: {len(documents)}")
    print(f"\nYou can now query the index using Azure AI Search.")

if __name__ == "__main__":
    main()


