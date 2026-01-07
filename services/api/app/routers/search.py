"""
Search API Endpoints
Provides multi-language, semantic, fuzzy, and voice search
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel, Field
import asyncpg

from ..core.database import get_db_connection
from ..services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])
search_service = SearchService()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SearchRequest(BaseModel):
    """Search request parameters"""
    query: str = Field(..., description="Search query text", min_length=1)
    limit: int = Field(20, description="Maximum number of results", ge=1, le=100)
    language: Optional[str] = Field(None, description="Language filter (en, hi, ta, es, zh, ar)")
    category: Optional[str] = Field(None, description="Category filter")


class SemanticSearchRequest(SearchRequest):
    """Semantic search request"""
    min_similarity: float = Field(0.5, description="Minimum similarity score", ge=0.0, le=1.0)


class FuzzySearchRequest(SearchRequest):
    """Fuzzy search request"""
    threshold: int = Field(70, description="Minimum fuzzy match score", ge=0, le=100)


class HybridSearchRequest(SearchRequest):
    """Hybrid search request"""
    use_semantic: bool = Field(True, description="Include semantic search")
    use_fuzzy: bool = Field(True, description="Include fuzzy search")


class VoiceSearchRequest(BaseModel):
    """Voice search request"""
    audio_text: str = Field(..., description="Transcribed audio text")
    limit: int = Field(20, ge=1, le=100)
    language: Optional[str] = None


class AutocompleteRequest(BaseModel):
    """Autocomplete request"""
    prefix: str = Field(..., description="Text prefix", min_length=1)
    limit: int = Field(10, ge=1, le=50)
    language: Optional[str] = None


class SearchResult(BaseModel):
    """Search result item"""
    id: str
    canonical_name: str
    category: str
    subcategory: Optional[str]
    names: dict
    common_uses: Optional[List[str]]
    match_type: str
    final_score: Optional[float]
    search_methods: Optional[List[str]]


class AutocompleteSuggestion(BaseModel):
    """Autocomplete suggestion"""
    suggestion: str
    language: str
    canonical_name: str
    category: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/multi-language")
async def multi_language_search(
    query: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(20, ge=1, le=100),
    language: Optional[str] = Query(None, description="Language filter"),
    category: Optional[str] = Query(None, description="Category filter"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Multi-language search across all ingredient names and aliases
    
    **Supports:**
    - Exact name matching
    - Partial name matching
    - Multi-language aliases (en, hi, ta, es, zh, ar)
    - Category filtering
    
    **Example:**
    ```
    GET /api/search/multi-language?query=haldi&language=hi
    GET /api/search/multi-language?query=turmeric&category=Spice
    ```
    """
    try:
        results = await search_service.multi_language_search(
            conn, query, limit=limit, language=language, category=category
        )
        
        return {
            "query": query,
            "language": language,
            "category": category,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/semantic")
async def semantic_search(
    request: SemanticSearchRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Semantic search using vector embeddings (OpenAI ada-002)
    
    **Features:**
    - Understands concepts and synonyms
    - No exact match required
    - Context-aware results
    
    **Requires:**
    - Embeddings must be generated first (run generate_embeddings.py)
    - pgvector extension enabled
    
    **Example:**
    ```json
    {
        "query": "yellow spice for curry",
        "limit": 10,
        "min_similarity": 0.6
    }
    ```
    """
    try:
        results = await search_service.embedding_service.semantic_search(
            conn,
            request.query,
            limit=request.limit,
            min_similarity=request.min_similarity,
            category_filter=request.category,
            language_filter=request.language
        )
        
        return {
            "query": request.query,
            "min_similarity": request.min_similarity,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        if "does not exist" in str(e) or "vector" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Semantic search unavailable. Embeddings may not be generated yet."
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fuzzy")
async def fuzzy_search(
    request: FuzzySearchRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Fuzzy search with typo tolerance using Levenshtein distance
    
    **Features:**
    - Handles spelling mistakes
    - Phonetically similar words
    - Partial matches
    
    **Example:**
    ```json
    {
        "query": "tumeric",
        "threshold": 70,
        "limit": 10
    }
    ```
    """
    try:
        results = await search_service.fuzzy_search(
            conn,
            request.query,
            limit=request.limit,
            threshold=request.threshold,
            language=request.language
        )
        
        return {
            "query": request.query,
            "threshold": request.threshold,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid")
async def hybrid_search(
    request: HybridSearchRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Hybrid search combining multiple strategies
    
    **Combines:**
    - Multi-language exact/partial matching
    - Fuzzy matching for typos
    - Semantic search for concepts
    
    **Returns:**
    - Ranked results from all methods
    - Score boosting for multi-method matches
    - Search methods used for each result
    
    **Example:**
    ```json
    {
        "query": "yellow powder spice",
        "limit": 15,
        "use_semantic": true,
        "use_fuzzy": true,
        "category": "Spice"
    }
    ```
    """
    try:
        results = await search_service.hybrid_search(
            conn,
            request.query,
            limit=request.limit,
            language=request.language,
            category=request.category,
            use_semantic=request.use_semantic,
            use_fuzzy=request.use_fuzzy
        )
        
        return {
            "query": request.query,
            "search_strategies": {
                "multi_language": True,
                "semantic": request.use_semantic,
                "fuzzy": request.use_fuzzy
            },
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice")
async def voice_search(
    request: VoiceSearchRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Voice search optimized for speech-to-text input
    
    **Features:**
    - More lenient fuzzy matching
    - Handles speech recognition errors
    - Multi-language voice support
    - Emphasis on semantic understanding
    
    **Usage:**
    1. Client captures audio
    2. Client transcribes using speech-to-text API
    3. Client sends transcribed text to this endpoint
    
    **Example:**
    ```json
    {
        "audio_text": "find yellow spice",
        "limit": 10,
        "language": "en"
    }
    ```
    """
    try:
        results = await search_service.voice_search(
            conn,
            request.audio_text,
            limit=request.limit,
            language=request.language
        )
        
        return {
            "transcribed_text": request.audio_text,
            "language": request.language,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autocomplete")
async def autocomplete(
    prefix: str = Query(..., description="Text prefix", min_length=1),
    limit: int = Query(10, ge=1, le=50),
    language: Optional[str] = Query(None, description="Language filter"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Autocomplete suggestions for search input
    
    **Returns:**
    - Ingredient names starting with prefix
    - Multi-language support
    - Category context
    
    **Example:**
    ```
    GET /api/search/autocomplete?prefix=tur&limit=5
    GET /api/search/autocomplete?prefix=हल&language=hi
    ```
    """
    try:
        suggestions = await search_service.autocomplete(
            conn, prefix, limit=limit, language=language
        )
        
        return {
            "prefix": prefix,
            "language": language,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def search_health():
    """Health check for search service"""
    return {
        "status": "healthy",
        "service": "search",
        "features": {
            "multi_language": True,
            "semantic_search": True,
            "fuzzy_search": True,
            "voice_search": True,
            "autocomplete": True
        }
    }
