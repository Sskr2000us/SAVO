"""
Embedding Service for Semantic Search
Generates and manages text embeddings using OpenAI ada-002
Enables semantic search with pgvector similarity
"""

import os
from typing import List, Dict, Any, Optional
import openai
from openai import OpenAI
import numpy as np
from datetime import datetime

class EmbeddingService:
    """Service for generating and managing embeddings"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = "text-embedding-ada-002"
        self.embedding_dimensions = 1536
    
    async def generate_text_embedding(self, text: str) -> List[float]:
        """
        Generate text embedding using OpenAI ada-002
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Clean and prepare text
            text = text.strip().replace("\n", " ")
            
            # Generate embedding
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    async def generate_ingredient_embedding(
        self, 
        ingredient_data: Dict[str, Any]
    ) -> List[float]:
        """
        Generate embedding for ingredient by combining multiple text fields
        
        Args:
            ingredient_data: Dictionary with ingredient fields
            
        Returns:
            Combined embedding vector
        """
        # Build comprehensive text representation
        text_parts = []
        
        # Add canonical name
        if ingredient_data.get("canonical_name"):
            text_parts.append(ingredient_data["canonical_name"])
        
        # Add multi-language names
        if ingredient_data.get("names"):
            names = ingredient_data["names"]
            if isinstance(names, dict):
                text_parts.extend(names.values())
        
        # Add category and subcategory
        if ingredient_data.get("category"):
            text_parts.append(ingredient_data["category"])
        if ingredient_data.get("subcategory"):
            text_parts.append(ingredient_data["subcategory"])
        
        # Add taste and aroma profiles
        if ingredient_data.get("taste_profile"):
            text_parts.extend(ingredient_data["taste_profile"])
        if ingredient_data.get("aroma_profile"):
            text_parts.extend(ingredient_data["aroma_profile"])
        
        # Add common uses
        if ingredient_data.get("common_uses"):
            text_parts.extend(ingredient_data["common_uses"])
        
        # Add embedding tags
        if ingredient_data.get("embedding_tags"):
            text_parts.extend(ingredient_data["embedding_tags"])
        
        # Combine all text parts
        combined_text = " ".join(str(part) for part in text_parts if part)
        
        # Generate embedding
        return await self.generate_text_embedding(combined_text)
    
    def calculate_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1 (higher is more similar)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    async def semantic_search(
        self,
        conn,
        query: str,
        limit: int = 20,
        min_similarity: float = 0.5,
        category_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        collapse_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search ingredients using semantic similarity
        
        Args:
            conn: Database connection
            query: Search query text
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
            category_filter: Optional category filter
            language_filter: Optional language code filter
            
        Returns:
            List of matching ingredients with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.generate_text_embedding(query)
            
            # Convert to PostgreSQL vector format
            vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            # Build SQL query with vector similarity
            if collapse_deprecated:
                sql = """
                    WITH candidates AS (
                        SELECT
                            public.resolve_master_ingredient_id(mi.id) AS resolved_id,
                            mi_res.canonical_name,
                            mi_res.category,
                            mi_res.subcategory,
                            mi_res.names,
                            mi_res.common_uses,
                            mi_res.embedding_tags,
                            1 - (ie.text_embedding <=> $1::vector) as similarity
                        FROM master_ingredients mi
                        JOIN ingredient_embeddings ie ON mi.id = ie.ingredient_id
                        JOIN master_ingredients mi_res
                          ON mi_res.id = public.resolve_master_ingredient_id(mi.id)
                        WHERE 1 - (ie.text_embedding <=> $1::vector) >= $2
                    ),
                    dedup AS (
                        SELECT DISTINCT ON (resolved_id)
                            resolved_id,
                            canonical_name,
                            category,
                            subcategory,
                            names,
                            common_uses,
                            embedding_tags,
                            similarity
                        FROM candidates
                        ORDER BY resolved_id, similarity DESC
                    )
                    SELECT
                        resolved_id AS id,
                        canonical_name,
                        category,
                        subcategory,
                        names,
                        common_uses,
                        embedding_tags,
                        similarity
                    FROM dedup
                    WHERE similarity >= $2
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
                        mi.embedding_tags,
                        1 - (ie.text_embedding <=> $1::vector) as similarity
                    FROM master_ingredients mi
                    JOIN ingredient_embeddings ie ON mi.id = ie.ingredient_id
                    WHERE 1 - (ie.text_embedding <=> $1::vector) >= $2
                """
            
            params = [vector_str, min_similarity]
            param_idx = 3
            
            # Add category filter
            if category_filter:
                sql += f" AND category = ${param_idx}" if collapse_deprecated else f" AND mi.category = ${param_idx}"
                params.append(category_filter)
                param_idx += 1
            
            # Add language filter (search in aliases)
            if language_filter:
                sql += f"""
                    AND EXISTS (
                        SELECT 1 FROM ingredient_aliases ia
                        WHERE ia.ingredient_id = {"resolved_id" if collapse_deprecated else "mi.id"}
                        AND ia.language_code = ${param_idx}
                    )
                """
                params.append(language_filter)
                param_idx += 1
            
            sql += f" ORDER BY similarity DESC LIMIT ${param_idx}"
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
                    "embedding_tags": row["embedding_tags"],
                    "similarity": float(row["similarity"]),
                    "match_type": "semantic"
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in semantic search: {e}")
            # Fallback to empty results
            return []
    
    async def batch_generate_embeddings(
        self,
        conn,
        batch_size: int = 50
    ) -> Dict[str, int]:
        """
        Generate embeddings for all ingredients without embeddings
        
        Args:
            conn: Database connection
            batch_size: Number of ingredients to process per batch
            
        Returns:
            Dictionary with generation statistics
        """
        stats = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
        
        try:
            # Get ingredients without embeddings
            ingredients = await conn.fetch("""
                SELECT 
                    mi.id,
                    mi.canonical_name,
                    mi.category,
                    mi.subcategory,
                    mi.names,
                    mi.taste_profile,
                    mi.aroma_profile,
                    mi.common_uses,
                    mi.embedding_tags
                FROM master_ingredients mi
                LEFT JOIN ingredient_embeddings ie ON mi.id = ie.ingredient_id
                WHERE ie.id IS NULL
                ORDER BY mi.canonical_name
            """)
            
            print(f"\nFound {len(ingredients)} ingredients without embeddings")
            
            for ingredient in ingredients:
                stats["processed"] += 1
                
                try:
                    # Generate embedding
                    embedding = await self.generate_ingredient_embedding(dict(ingredient))
                    
                    # Convert to PostgreSQL vector format
                    vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    
                    # Insert embedding
                    await conn.execute("""
                        INSERT INTO ingredient_embeddings (
                            ingredient_id,
                            text_embedding,
                            embedding_model,
                            embedding_version
                        ) VALUES ($1, $2::vector, $3, $4)
                    """, 
                        ingredient["id"],
                        vector_str,
                        self.embedding_model,
                        "v1"
                    )
                    
                    stats["success"] += 1
                    print(f"✅ Generated embedding for: {ingredient['canonical_name']}")
                    
                except Exception as e:
                    stats["failed"] += 1
                    print(f"❌ Failed for {ingredient['canonical_name']}: {e}")
                    continue
            
            return stats
            
        except Exception as e:
            print(f"Error in batch generation: {e}")
            raise
