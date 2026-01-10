"""
Search Service for Multi-Language Ingredient Search
Supports: multi-language, fuzzy matching, semantic search, voice search
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

from .embedding_service import EmbeddingService


class SearchService:
    """Comprehensive ingredient search service"""
    
    def __init__(self):
        """Initialize search service with embedding service"""
        self.embedding_service = EmbeddingService()
        self.fuzzy_threshold = 70  # Minimum fuzzy match score (0-100)
    
    async def multi_language_search(
        self,
        conn,
        query: str,
        limit: int = 20,
        language: Optional[str] = None,
        category: Optional[str] = None,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search ingredients across all languages using aliases
        
        Args:
            conn: Database connection
            query: Search query text
            limit: Maximum number of results
            language: Optional language code filter (en, hi, ta, es, zh, ar)
            category: Optional category filter
            
        Returns:
            List of matching ingredients
        """
        try:
            # Build SQL query
            if collapse_deprecated:
                params = [query]
                param_idx = 2

                candidates_extra = ""
                if language:
                    candidates_extra += f" AND ia.language_code = ${param_idx}"
                    params.append(language)
                    param_idx += 1
                if category:
                    candidates_extra += f" AND mi_res.category = ${param_idx}"
                    params.append(category)
                    param_idx += 1

                sql = f"""
                    WITH candidates AS (
                        SELECT
                            public.resolve_master_ingredient_id(mi.id) AS resolved_id,
                            mi_res.canonical_name,
                            mi_res.category,
                            mi_res.subcategory,
                            mi_res.names,
                            mi_res.common_uses,
                            mi_res.taste_profile,
                            mi_res.embedding_tags,
                            ia.alias_name as matched_alias,
                            ia.language_code as matched_language,
                            CASE
                                WHEN LOWER(mi.canonical_name) = LOWER($1) THEN 100
                                WHEN LOWER(ia.alias_name) = LOWER($1) THEN 95
                                WHEN LOWER(mi.canonical_name) LIKE LOWER($1 || '%') THEN 90
                                WHEN LOWER(ia.alias_name) LIKE LOWER($1 || '%') THEN 85
                                WHEN LOWER(mi.canonical_name) LIKE LOWER('%' || $1 || '%') THEN 70
                                WHEN LOWER(ia.alias_name) LIKE LOWER('%' || $1 || '%') THEN 65
                                ELSE 50
                            END as relevance_score
                        FROM master_ingredients mi
                        JOIN master_ingredients mi_res
                          ON mi_res.id = public.resolve_master_ingredient_id(mi.id)
                        LEFT JOIN ingredient_aliases ia ON mi.id = ia.ingredient_id
                        WHERE (
                            LOWER(mi.canonical_name) LIKE LOWER('%' || $1 || '%')
                            OR LOWER(ia.alias_name) LIKE LOWER('%' || $1 || '%')
                        )
                        {candidates_extra}
                    ),
                    dedup AS (
                        SELECT DISTINCT ON (resolved_id)
                            resolved_id,
                            canonical_name,
                            category,
                            subcategory,
                            names,
                            common_uses,
                            taste_profile,
                            embedding_tags,
                            matched_alias,
                            matched_language,
                            relevance_score
                        FROM candidates
                        ORDER BY resolved_id, relevance_score DESC
                    )
                    SELECT
                        resolved_id AS id,
                        canonical_name,
                        category,
                        subcategory,
                        names,
                        common_uses,
                        taste_profile,
                        embedding_tags,
                        matched_alias,
                        matched_language,
                        relevance_score
                    FROM dedup
                    ORDER BY relevance_score DESC, canonical_name
                    LIMIT ${param_idx}
                """
                params.append(limit)
            else:
                sql = """
                    SELECT DISTINCT
                        mi.id,
                        mi.canonical_name,
                        mi.category,
                        mi.subcategory,
                        mi.names,
                        mi.common_uses,
                        mi.taste_profile,
                        mi.embedding_tags,
                        ia.alias_name as matched_alias,
                        ia.language_code as matched_language,
                        CASE
                            WHEN LOWER(mi.canonical_name) = LOWER($1) THEN 100
                            WHEN LOWER(ia.alias_name) = LOWER($1) THEN 95
                            WHEN LOWER(mi.canonical_name) LIKE LOWER($1 || '%') THEN 90
                            WHEN LOWER(ia.alias_name) LIKE LOWER($1 || '%') THEN 85
                            WHEN LOWER(mi.canonical_name) LIKE LOWER('%' || $1 || '%') THEN 70
                            WHEN LOWER(ia.alias_name) LIKE LOWER('%' || $1 || '%') THEN 65
                            ELSE 50
                        END as relevance_score
                    FROM master_ingredients mi
                    LEFT JOIN ingredient_aliases ia ON mi.id = ia.ingredient_id
                    WHERE (
                        LOWER(mi.canonical_name) LIKE LOWER('%' || $1 || '%')
                        OR LOWER(ia.alias_name) LIKE LOWER('%' || $1 || '%')
                    )
                """

                params = [query]
                param_idx = 2

                # Add language filter
                if language:
                    sql += f" AND ia.language_code = ${param_idx}"
                    params.append(language)
                    param_idx += 1

                # Add category filter
                if category:
                    sql += f" AND mi.category = ${param_idx}"
                    params.append(category)
                    param_idx += 1

                sql += f" ORDER BY relevance_score DESC, mi.canonical_name LIMIT ${param_idx}"
                params.append(limit)
            
            # Execute query
            results = await conn.fetch(sql, *params)
            
            # Format results
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "id": str(row["id"]),
                    "canonical_name": row["canonical_name"],
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "names": row["names"],
                    "common_uses": row["common_uses"],
                    "taste_profile": row["taste_profile"],
                    "embedding_tags": row["embedding_tags"],
                    "matched_alias": row["matched_alias"],
                    "matched_language": row["matched_language"],
                    "relevance_score": int(row["relevance_score"]),
                    "match_type": "exact" if row["relevance_score"] >= 90 else "partial"
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in multi-language search: {e}")
            return []
    
    async def fuzzy_search(
        self,
        conn,
        query: str,
        limit: int = 20,
        threshold: Optional[int] = None,
        language: Optional[str] = None,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fuzzy search for typo tolerance using Levenshtein distance
        
        Args:
            conn: Database connection
            query: Search query text (may contain typos)
            limit: Maximum number of results
            threshold: Minimum fuzzy match score (0-100), default 70
            language: Optional language filter
            
        Returns:
            List of matching ingredients with fuzzy scores
        """
        threshold = threshold or self.fuzzy_threshold
        
        try:
            # Get all ingredient names and aliases
            if collapse_deprecated:
                sql = """
                    SELECT
                        public.resolve_master_ingredient_id(mi.id) AS resolved_id,
                        mi_res.canonical_name,
                        mi_res.category,
                        mi_res.subcategory,
                        mi_res.names,
                        mi_res.common_uses,
                        ia.alias_name,
                        ia.language_code
                    FROM master_ingredients mi
                    JOIN master_ingredients mi_res
                      ON mi_res.id = public.resolve_master_ingredient_id(mi.id)
                    LEFT JOIN ingredient_aliases ia ON mi.id = ia.ingredient_id
                """
            else:
                sql = """
                    SELECT 
                        mi.id,
                        mi.canonical_name,
                        mi.category,
                        mi.subcategory,
                        mi.names,
                        mi.common_uses,
                        ia.alias_name,
                        ia.language_code
                    FROM master_ingredients mi
                    LEFT JOIN ingredient_aliases ia ON mi.id = ia.ingredient_id
                """
            
            params = []
            if language:
                sql += " WHERE ia.language_code = $1"
                params.append(language)
            
            results = await conn.fetch(sql, *params)
            
            # Build searchable text list
            search_items = {}  # {text: ingredient_data}
            for row in results:
                ingredient_id = str(row["resolved_id"] if collapse_deprecated else row["id"])
                
                # Add canonical name
                search_items[row["canonical_name"]] = {
                    "id": ingredient_id,
                    "canonical_name": row["canonical_name"],
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "names": row["names"],
                    "common_uses": row["common_uses"],
                    "matched_text": row["canonical_name"],
                    "matched_language": "en",
                    "is_alias": False
                }
                
                # Add alias
                if row["alias_name"]:
                    search_items[row["alias_name"]] = {
                        "id": ingredient_id,
                        "canonical_name": row["canonical_name"],
                        "category": row["category"],
                        "subcategory": row["subcategory"],
                        "names": row["names"],
                        "common_uses": row["common_uses"],
                        "matched_text": row["alias_name"],
                        "matched_language": row["language_code"],
                        "is_alias": True
                    }
            
            # Perform fuzzy matching
            matches = process.extract(
                query, 
                search_items.keys(), 
                scorer=fuzz.token_sort_ratio,
                limit=limit * 2  # Get more to deduplicate
            )
            
            # Filter by threshold and deduplicate by ingredient_id
            seen_ids = set()
            formatted_results = []
            
            for matched_text, score in matches:
                if score >= threshold:
                    ingredient_data = search_items[matched_text]
                    ingredient_id = ingredient_data["id"]
                    
                    # Skip if already seen (prefer higher scoring matches)
                    if ingredient_id in seen_ids:
                        continue
                    
                    seen_ids.add(ingredient_id)
                    
                    formatted_results.append({
                        "id": ingredient_id,
                        "canonical_name": ingredient_data["canonical_name"],
                        "category": ingredient_data["category"],
                        "subcategory": ingredient_data["subcategory"],
                        "names": ingredient_data["names"],
                        "common_uses": ingredient_data["common_uses"],
                        "matched_text": ingredient_data["matched_text"],
                        "matched_language": ingredient_data["matched_language"],
                        "fuzzy_score": score,
                        "match_type": "fuzzy",
                        "is_alias": ingredient_data["is_alias"]
                    })
                    
                    if len(formatted_results) >= limit:
                        break
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in fuzzy search: {e}")
            return []
    
    async def hybrid_search(
        self,
        conn,
        query: str,
        limit: int = 20,
        language: Optional[str] = None,
        category: Optional[str] = None,
        use_semantic: bool = True,
        use_fuzzy: bool = True,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining multiple search strategies
        
        Args:
            conn: Database connection
            query: Search query text
            limit: Maximum number of results
            language: Optional language filter
            category: Optional category filter
            use_semantic: Whether to include semantic search
            use_fuzzy: Whether to include fuzzy search
            
        Returns:
            Combined and ranked results from multiple search methods
        """
        all_results = {}  # {ingredient_id: result_data}
        
        # 1. Multi-language exact/partial match (highest priority)
        ml_results = await self.multi_language_search(
            conn, query, limit=limit, language=language, category=category, collapse_deprecated=collapse_deprecated
        )
        for result in ml_results:
            ingredient_id = result["id"]
            result["search_methods"] = ["multi_language"]
            result["final_score"] = result["relevance_score"]
            all_results[ingredient_id] = result
        
        # 2. Fuzzy search for typo tolerance
        if use_fuzzy and len(all_results) < limit:
            fuzzy_results = await self.fuzzy_search(
                conn, query, limit=limit, language=language, collapse_deprecated=collapse_deprecated
            )
            for result in fuzzy_results:
                ingredient_id = result["id"]
                if ingredient_id in all_results:
                    # Boost score if found by multiple methods
                    all_results[ingredient_id]["search_methods"].append("fuzzy")
                    all_results[ingredient_id]["fuzzy_score"] = result["fuzzy_score"]
                    all_results[ingredient_id]["final_score"] += result["fuzzy_score"] * 0.5
                else:
                    result["search_methods"] = ["fuzzy"]
                    result["final_score"] = result["fuzzy_score"]
                    all_results[ingredient_id] = result
        
        # 3. Semantic search for concept matching
        if use_semantic and len(all_results) < limit:
            try:
                semantic_results = await self.embedding_service.semantic_search(
                    conn, query, limit=limit, 
                    category_filter=category, language_filter=language,
                    collapse_deprecated=collapse_deprecated,
                )
                for result in semantic_results:
                    ingredient_id = result["id"]
                    semantic_score = result["similarity"] * 100  # Convert to 0-100 scale
                    
                    if ingredient_id in all_results:
                        # Boost score if found by multiple methods
                        all_results[ingredient_id]["search_methods"].append("semantic")
                        all_results[ingredient_id]["similarity"] = result["similarity"]
                        all_results[ingredient_id]["final_score"] += semantic_score * 0.7
                    else:
                        result["search_methods"] = ["semantic"]
                        result["final_score"] = semantic_score
                        all_results[ingredient_id] = result
            except Exception as e:
                print(f"Semantic search failed (may need embeddings): {e}")
        
        # Sort by final score and return top results
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )
        
        return sorted_results[:limit]
    
    async def voice_search(
        self,
        conn,
        audio_text: str,
        limit: int = 20,
        language: Optional[str] = None,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search optimized for voice input (speech-to-text)
        More lenient fuzzy matching due to speech recognition errors
        
        Args:
            conn: Database connection
            audio_text: Transcribed text from speech recognition
            limit: Maximum number of results
            language: Optional language filter
            
        Returns:
            Search results optimized for voice input
        """
        # Voice search uses hybrid search with:
        # - Lower fuzzy threshold (more lenient)
        # - Emphasis on semantic search (concept matching)
        # - Multi-language support for cross-language voice input
        
        # Temporarily lower fuzzy threshold for voice
        original_threshold = self.fuzzy_threshold
        self.fuzzy_threshold = 60  # More lenient for speech recognition errors
        
        try:
            results = await self.hybrid_search(
                conn,
                audio_text,
                limit=limit,
                language=language,
                use_semantic=True,
                use_fuzzy=True,
                collapse_deprecated=collapse_deprecated,
            )
            
            # Add voice search metadata
            for result in results:
                result["input_method"] = "voice"
                result["transcribed_text"] = audio_text
            
            return results
            
        finally:
            # Restore original threshold
            self.fuzzy_threshold = original_threshold
    
    async def autocomplete(
        self,
        conn,
        prefix: str,
        limit: int = 10,
        language: Optional[str] = None,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Autocomplete suggestions for search input
        
        Args:
            conn: Database connection
            prefix: Text prefix to complete
            limit: Maximum number of suggestions
            language: Optional language filter
            
        Returns:
            List of autocomplete suggestions
        """
        try:
            if collapse_deprecated:
                sql = """
                    SELECT DISTINCT
                        ia.alias_name as suggestion,
                        ia.language_code,
                        mi_res.canonical_name,
                        mi_res.category
                    FROM ingredient_aliases ia
                    JOIN master_ingredients mi ON ia.ingredient_id = mi.id
                    JOIN master_ingredients mi_res
                      ON mi_res.id = public.resolve_master_ingredient_id(mi.id)
                    WHERE LOWER(ia.alias_name) LIKE LOWER($1 || '%')
                """
            else:
                sql = """
                    SELECT DISTINCT
                        ia.alias_name as suggestion,
                        ia.language_code,
                        mi.canonical_name,
                        mi.category
                    FROM ingredient_aliases ia
                    JOIN master_ingredients mi ON ia.ingredient_id = mi.id
                    WHERE LOWER(ia.alias_name) LIKE LOWER($1 || '%')
                """
            
            params = [prefix]
            
            if language:
                sql += " AND ia.language_code = $2"
                params.append(language)
                sql += " ORDER BY ia.alias_name LIMIT $3"
                params.append(limit)
            else:
                sql += " ORDER BY ia.alias_name LIMIT $2"
                params.append(limit)
            
            results = await conn.fetch(sql, *params)
            
            suggestions = []
            for row in results:
                suggestions.append({
                    "suggestion": row["suggestion"],
                    "language": row["language_code"],
                    "canonical_name": row["canonical_name"],
                    "category": row["category"]
                })
            
            return suggestions
            
        except Exception as e:
            print(f"Error in autocomplete: {e}")
            return []
