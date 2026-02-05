"""
02 - Upload PDF Documents to Azure AI Search
Processes PDF files from data/default/documents and uploads them to Azure AI Search with embeddings.

Usage:
    python 02_upload_documents.py --search_endpoint <endpoint> --openai_endpoint <endpoint> --embedding_model <model>

Prerequisites:
    - Run 01_create_search_index.py first
    - PDF files in data/default/documents folder
    - Azure OpenAI embedding model deployed
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from azure.ai.inference import EmbeddingsClient
from azure.search.documents import SearchClient
from pypdf import PdfReader
from azure_credential_utils import get_azure_credential

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--search_endpoint", required=True, help="Azure AI Search endpoint")
p.add_argument("--ai_project_endpoint", required=True, help="Azure AI Project endpoint")
p.add_argument("--embedding_model", required=True, help="Embedding model deployment name")
p.add_argument("--data_folder", default="data/default/documents", help="Folder containing PDF files")
p.add_argument("--chunk_size", type=int, default=1024, help="Maximum chunk size in tokens")
args = p.parse_args()

SEARCH_ENDPOINT = args.search_endpoint
AI_PROJECT_ENDPOINT = args.ai_project_endpoint
EMBEDDING_MODEL = args.embedding_model
DATA_FOLDER = args.data_folder
CHUNK_SIZE = args.chunk_size

INDEX_NAME = "call_transcripts_index"

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

def chunk_data(text: str, tokens_per_chunk: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks based on token count (simplified version).
    
    Note: This is a simplified version. For production, consider using tiktoken
    for accurate token counting based on the specific model.
    """
    # Approximate: 1 token ≈ 4 characters
    chars_per_chunk = tokens_per_chunk * 4
    
    # Split on sentence boundaries where possible
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_len = len(sentence)
        
        # If single sentence exceeds chunk size, add it anyway
        if sentence_len > chars_per_chunk:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            chunks.append(sentence)
            current_chunk = []
            current_length = 0
            continue
        
        # Check if adding this sentence would exceed chunk size
        if current_length + sentence_len > chars_per_chunk and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks if chunks else [text]

# ============================================================================
# Embedding Generation
# ============================================================================

def get_embeddings_client():
    """Create Azure AI Foundry Inference EmbeddingsClient (matching reference repo)."""
    credential = get_azure_credential()
    
    # Construct inference endpoint from AI Project endpoint
    inference_endpoint = f"https://{urlparse(AI_PROJECT_ENDPOINT).netloc}/models"
    
    return EmbeddingsClient(
        endpoint=inference_endpoint,
        credential=credential,
        credential_scopes=["https://ai.azure.com/.default"],
    )

def get_embedding(client: EmbeddingsClient, text: str) -> list[float]:
    """Generate embedding for text using EmbeddingsClient (matching reference repo)."""
    try:
        response = client.embed(model=EMBEDDING_MODEL, input=[text])
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        raise

# ============================================================================
# Document Preparation
# ============================================================================

def prepare_search_doc(content: str, document_id: str, source_filename: str, embeddings_client: EmbeddingsClient) -> list[dict]:
    """Prepare search documents from content (matching reference repo structure)."""
    chunks = chunk_data(content)
    docs = []
    
    for idx, chunk in enumerate(chunks, 1):
        chunk_id = f"{document_id}_{str(idx).zfill(2)}"
        
        try:
            embedding = get_embedding(embeddings_client, chunk)
        except Exception as e:
            print(f"    Warning: Error getting embedding (attempt 1): {e}")
            try:
                # Retry once
                import time
                time.sleep(2)
                embedding = get_embedding(embeddings_client, chunk)
            except Exception as e2:
                print(f"    Warning: Error getting embedding (attempt 2): {e2}, using empty vector")
                embedding = []
        
        doc = {
            "id": chunk_id,
            "chunk_id": chunk_id,
            "title": source_filename,
            "content": chunk,
            "url": source_filename,
            "contentVector": embedding
        }
        docs.append(doc)
    print(f"  Prepared {len(docs)} chunks for document '{source_filename}'")
    return docs

# ============================================================================
# Main Processing
# ============================================================================

def upload_documents():
    """Process PDFs and upload to search index."""
    
    # Find PDF files
    data_dir = Path(DATA_FOLDER)
    if not data_dir.exists():
        print(f"\n✗ Error: Data folder not found: {data_dir}")
        print("  Please ensure PDF files are in the correct location")
        sys.exit(1)
    
    pdf_files = list(data_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"✗ No PDF files found in: {data_dir}")
        sys.exit(1)
    
    # Initialize clients
    embeddings_client = get_embeddings_client()
    credential = get_azure_credential()
    search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, credential)
    
    # Process each PDF
    all_docs = []
    counter = 0
    
    for pdf_path in pdf_files:
        pages = extract_pages_from_pdf(pdf_path)
        
        # Combine all pages into single content
        full_content = ' '.join([page_text for _, page_text in pages])
        document_id = pdf_path.stem
        
        # Prepare search documents
        docs = prepare_search_doc(full_content, document_id, pdf_path.name, embeddings_client)
        
        all_docs.extend(docs)
        counter += 1
        
        # Upload in batches of 10 documents
        if len(all_docs) >= 10:
            result = search_client.upload_documents(documents=all_docs)
            all_docs = []
    
    # Upload remaining documents
    if all_docs:
        result = search_client.upload_documents(documents=all_docs)
    
    print(f"✓ Processed {counter} files")

try:
    upload_documents()
except Exception as e:
    print(f"\n✗ Error uploading documents: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
