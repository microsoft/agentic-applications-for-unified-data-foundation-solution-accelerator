"""
01 - Create Azure AI Search Index
Creates a search index with vector search and semantic configuration for document search.

Usage:
    python 01_create_search_index.py --search_endpoint <endpoint> --openai_endpoint <endpoint> --embedding_model <model>

Prerequisites:
    - Azure AI Search service deployed
    - Azure OpenAI embedding model deployed
    - Appropriate permissions (Search Index Data Contributor)
"""

import argparse
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from azure.identity import DefaultAzureCredential
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
from azure_credential_utils import get_azure_credential

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--search_endpoint", required=True, help="Azure AI Search endpoint")
p.add_argument("--openai_endpoint", required=True, help="Azure OpenAI endpoint")
p.add_argument("--embedding_model", required=True, help="Embedding model deployment name")
args = p.parse_args()

SEARCH_ENDPOINT = args.search_endpoint
OPENAI_ENDPOINT = args.openai_endpoint
EMBEDDING_MODEL = args.embedding_model

INDEX_NAME = "call_transcripts_index"

# Embedding dimensions by model
EMBEDDING_DIMENSIONS = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}

def create_search_index():
    """Create or update the search index with integrated vectorizer."""
    
    credential = get_azure_credential()
    index_client = SearchIndexClient(SEARCH_ENDPOINT, credential)
    
    dimensions = EMBEDDING_DIMENSIONS.get(EMBEDDING_MODEL, 1536)
    
    # Define index fields (matching reference repo schema)
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.String),
        SearchField(name="title", type=SearchFieldDataType.String),
        SearchField(name="content", type=SearchFieldDataType.String),
        SearchField(name="url", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=dimensions,
            vector_search_profile_name="myHnswProfile"
        )
    ]
    
    # Vector search configuration (matching reference repo)
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="myHnsw")
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw",
                vectorizer_name="myOpenAI"
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="myOpenAI",
                kind="azureOpenAI",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=OPENAI_ENDPOINT,
                    deployment_name=EMBEDDING_MODEL,
                    model_name=EMBEDDING_MODEL
                )
            )
        ]
    )
    
    # Semantic configuration for hybrid search
    semantic_config = SemanticConfiguration(
        name="my-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            keywords_fields=[SemanticField(field_name="chunk_id")],
            content_fields=[SemanticField(field_name="content")]
        )
    )
    
    semantic_search = SemanticSearch(configurations=[semantic_config])
    
    # Create index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )
    
    result = index_client.create_or_update_index(index)
    
    return result

try:
    create_search_index()
    print("✓ Search index created")
except Exception as e:
    print(f"\n✗ Error creating search index: {e}")
    sys.exit(1)
