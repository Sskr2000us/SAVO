"""
Generate Embeddings for All Ingredients
Creates text embeddings using OpenAI ada-002 for semantic search
Requires: OPENAI_API_KEY and DATABASE_URL environment variables
"""

import os
import sys
import asyncio
from datetime import datetime
import asyncpg

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding_service import EmbeddingService

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def enable_pgvector(conn):
    """Enable pgvector extension if not already enabled"""
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("✅ pgvector extension enabled")
    except Exception as e:
        print(f"⚠️  Warning: Could not enable pgvector extension: {e}")
        print("   You may need to enable it manually in Supabase Dashboard")

async def main():
    """Main function to generate embeddings"""
    
    print("\n" + "="*80)
    print("SAVO INGREDIENT EMBEDDINGS GENERATOR")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*80)
    
    # Check environment variables
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        # Connect to database
        print("\nConnecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        # Enable pgvector extension
        print("\nEnabling pgvector extension...")
        await enable_pgvector(conn)
        
        # Initialize embedding service
        print("\nInitializing OpenAI embedding service...")
        embedding_service = EmbeddingService()
        print(f"✅ Using model: {embedding_service.embedding_model}")
        print(f"   Embedding dimensions: {embedding_service.embedding_dimensions}")
        
        # Generate embeddings
        print("\n" + "-"*80)
        print("GENERATING EMBEDDINGS")
        print("-"*80)
        
        stats = await embedding_service.batch_generate_embeddings(conn)
        
        # Print results
        print("\n" + "="*80)
        print("🎉 EMBEDDING GENERATION COMPLETE!")
        print(f"   • Processed: {stats['processed']} ingredients")
        print(f"   • Success: {stats['success']} embeddings created")
        print(f"   • Failed: {stats['failed']} errors")
        print(f"   • Skipped: {stats['skipped']} already exist")
        print("="*80 + "\n")
        
        # Test semantic search
        if stats['success'] > 0:
            print("\n" + "-"*80)
            print("TESTING SEMANTIC SEARCH")
            print("-"*80)
            
            test_queries = [
                "yellow spice for curries",
                "protein for vegetarian dishes",
                "leafy green vegetable"
            ]
            
            for query in test_queries:
                print(f"\nQuery: '{query}'")
                results = await embedding_service.semantic_search(
                    conn,
                    query,
                    limit=3,
                    min_similarity=0.5
                )
                
                if results:
                    for i, result in enumerate(results, 1):
                        print(f"  {i}. {result['canonical_name']} "
                              f"({result['category']}) - "
                              f"Similarity: {result['similarity']:.3f}")
                else:
                    print("  No results found")
        
        # Close connection
        await conn.close()
        print("\n✅ Database connection closed")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
