"""
Modal API for Story Processing

Stateless HTTP API service for content extraction and story chunking.
Uses Supabase Storage for all file operations.
"""

import modal
import os
from typing import Dict, Any, Optional

# Environment detection
IS_DEV = os.environ.get("MODAL_ENVIRONMENT", "dev") != "prod"
APP_NAME = "nighttime-story-prep-api-dev" if IS_DEV else "nighttime-story-prep-api"

print(f"🚀 Running Modal API in {'DEVELOPMENT' if IS_DEV else 'PRODUCTION'} mode")
print(f"   App: {APP_NAME}")

# Create Modal app
app = modal.App(APP_NAME)

# Define image with dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "anthropic>=0.69.0",
        "claude-agent-sdk>=0.1.0",
        "supabase>=2.0.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.3.0",
        "requests>=2.32.0",
        "pyyaml>=6.0.0",
        "python-dateutil>=2.9.0",
        "fastapi[standard]",
    )
    .add_local_file("modal-api/src/supabase_storage.py", "/root/src/supabase_storage.py")
    .add_local_file("modal-api/src/content_extraction_agent.py", "/root/src/content_extraction_agent.py")
    .add_local_file("modal-api/src/chunker.py", "/root/src/chunker.py")
    .add_local_file("modal-api/src/email_parser.py", "/root/src/email_parser.py")
)


def verify_api_key(authorization: Optional[str] = None) -> bool:
    """
    Verify API key from Authorization header.

    Args:
        authorization: Authorization header value (should be "Bearer <key>")

    Returns:
        True if valid, False otherwise
    """
    if not authorization:
        return False

    expected_key = os.environ.get("MODAL_API_KEY")
    if not expected_key:
        print("⚠️  Warning: MODAL_API_KEY not set in environment")
        return True  # Allow requests if no key is configured

    # Extract bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    token = parts[1]
    return token == expected_key


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("story-prep-secrets"),
        modal.Secret.from_name("supabase-secrets"),
    ],
    timeout=600,
)
@modal.fastapi_endpoint(method="POST")
async def extract_content_endpoint(email_data: dict, storage_id: str):
    """Extract content from email data and store in Supabase."""
    from fastapi import HTTPException
    from src.content_extraction_agent import extract_content_async
    from src.supabase_storage import SupabaseStorage
    
    # Note: FastAPI will inject the Authorization header if we use Header dependency
    # For now, we'll handle auth in the function body
    
    print(f"\n{'='*80}")
    print(f"📥 EXTRACT CONTENT REQUEST")
    print(f"{'='*80}")
    print(f"Storage ID: {storage_id}")
    print(f"Subject: {email_data.get('subject', 'N/A')}")
    print(f"From: {email_data.get('from', 'N/A')}")

    try:
        # Initialize Supabase Storage
        storage = SupabaseStorage()

        # Extract content
        result = await extract_content_async(email_data, storage_id, storage)

        print(f"\n✅ Content extraction successful")
        print(f"   Content URL: {result['content_url']}")
        print(f"   Title: {result['metadata'].get('title')}")
        print(f"   Word count: {result['metadata'].get('word_count')}")
        print(f"{'='*80}\n")

        return {
            "status": "success",
            "content_url": result["content_url"],
            "metadata": result["metadata"]
        }

    except Exception as e:
        print(f"\n❌ Content extraction error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("story-prep-secrets"),
        modal.Secret.from_name("supabase-secrets"),
    ],
    timeout=900,
)
@modal.fastapi_endpoint(method="POST")
async def chunk_story_endpoint(content_url: str, storage_id: str, target_words: int = 5000):
    """Chunk story content from Supabase Storage."""
    from fastapi import HTTPException
    from src.chunker import chunk_story
    from src.supabase_storage import SupabaseStorage

    print(f"\n{'='*80}")
    print(f"✂️  CHUNK STORY REQUEST")
    print(f"{'='*80}")
    print(f"Storage ID: {storage_id}")
    print(f"Content URL: {content_url}")
    print(f"Target words: {target_words}")

    try:
        # Initialize Supabase Storage
        storage = SupabaseStorage()

        # Chunk the story (always uses AgentChunker)
        result = await chunk_story(
            content_url=content_url,
            storage_id=storage_id,
            target_words=target_words,
            storage=storage
        )

        print(f"\n✅ Chunking successful")
        print(f"   Total chunks: {result['total_chunks']}")
        print(f"   Total words: {result['total_words']}")
        print(f"   Strategy used: {result['chunking_strategy']}")
        print(f"{'='*80}\n")

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        print(f"\n❌ Chunking error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("story-prep-secrets"),
        modal.Secret.from_name("supabase-secrets"),
    ],
    timeout=30,
)
@modal.fastapi_endpoint(method="GET")
def health_endpoint():
    """Health check endpoint."""
    from src.supabase_storage import SupabaseStorage
    
    services = {}

    # Check Anthropic API
    try:
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            services["anthropic_api"] = "ok"
        else:
            services["anthropic_api"] = "error: key not set"
    except Exception as e:
        services["anthropic_api"] = f"error: {str(e)}"

    # Check Supabase Storage
    try:
        storage = SupabaseStorage()
        if storage.health_check():
            services["supabase_storage"] = "ok"
        else:
            services["supabase_storage"] = "error: health check failed"
    except Exception as e:
        services["supabase_storage"] = f"error: {str(e)}"

    # Overall status
    all_healthy = all(status == "ok" for status in services.values())
    overall_status = "healthy" if all_healthy else "degraded"

    print(f"🏥 Health check: {overall_status}")
    for service, status in services.items():
        print(f"   {service}: {status}")

    return {
        "status": overall_status,
        "services": services
    }


# Local testing entrypoint
@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.

    Run with: modal run main.py
    """
    print("Modal API is ready to deploy!")
    print(f"App name: {APP_NAME}")
    print("\nTo deploy:")
    print(f"  modal deploy modal-api/main.py")
    print("\nEndpoints:")
    print("  POST /extract-content")
    print("  POST /chunk-story")
    print("  GET /health")
