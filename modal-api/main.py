"""
Modal API for Story Processing

Stateless HTTP API service for content extraction and story chunking.
Uses Supabase Storage for all file operations.
"""

import modal
import os
from typing import Dict, Any, Optional
from fastapi import HTTPException, Header, Request
from fastapi.responses import JSONResponse

from src.content_extraction_agent import extract_content
from src.chunker import chunk_story
from src.supabase_storage import SupabaseStorage

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
        "fastapi",
    )
    .add_local_file("src/supabase_storage.py", "/root/src/supabase_storage.py")
    .add_local_file("src/content_extraction_agent.py", "/root/src/content_extraction_agent.py")
    .add_local_file("src/chunker.py", "/root/src/chunker.py")
    .add_local_file("src/email_parser.py", "/root/src/email_parser.py")
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
@modal.web_endpoint(method="POST")
async def extract_content_endpoint(request: Request):
    """
    Extract content from email data and store in Supabase.

    POST /extract-content
    Headers:
        Authorization: Bearer <api-key>
    Body:
        {
            "email_data": {
                "text": "...",
                "html": "...",
                "subject": "...",
                "from": "..."
            },
            "storage_id": "unique-id-for-story"
        }

    Response:
        {
            "content_url": "story-content/unique-id/content.txt",
            "metadata": {
                "title": "...",
                "author": "...",
                "extraction_method": "agent|fallback",
                "word_count": 12500
            }
        }
    """
    # Verify authentication
    auth_header = request.headers.get("authorization")
    if not verify_api_key(auth_header):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Invalid or missing API key"}
        )

    try:
        # Parse request body
        body = await request.json()
        email_data = body.get("email_data")
        storage_id = body.get("storage_id")

        if not email_data or not storage_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Bad Request", "message": "Missing email_data or storage_id"}
            )

        print(f"\n{'='*80}")
        print(f"📥 EXTRACT CONTENT REQUEST")
        print(f"{'='*80}")
        print(f"Storage ID: {storage_id}")
        print(f"Subject: {email_data.get('subject', 'N/A')}")
        print(f"From: {email_data.get('from', 'N/A')}")

        # Initialize Supabase Storage
        storage = SupabaseStorage()

        # Extract content
        result = extract_content(email_data, storage_id, storage)

        if not result:
            return JSONResponse(
                status_code=422,
                content={"error": "Extraction Failed", "message": "Could not extract story content from email"}
            )

        print(f"\n✅ Content extraction successful")
        print(f"   Content URL: {result['content_url']}")
        print(f"   Title: {result['metadata'].get('title')}")
        print(f"   Word count: {result['metadata'].get('word_count')}")
        print(f"{'='*80}\n")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "content_url": result["content_url"],
                "metadata": result["metadata"]
            }
        )

    except Exception as e:
        print(f"\n❌ Content extraction error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")

        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "message": str(e)}
        )


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("story-prep-secrets"),
        modal.Secret.from_name("supabase-secrets"),
    ],
    timeout=900,  # Chunking can take longer
)
@modal.web_endpoint(method="POST")
async def chunk_story_endpoint(request: Request):
    """
    Chunk story content from Supabase Storage.

    POST /chunk-story
    Headers:
        Authorization: Bearer <api-key>
    Body:
        {
            "content_url": "story-content/unique-id/content.txt",
            "storage_id": "unique-id-for-story",
            "target_words": 5000
        }

    Response:
        {
            "chunks": [
                {
                    "chunk_number": 1,
                    "url": "story-chunks/unique-id/chunk_001.txt",
                    "word_count": 4998
                },
                ...
            ],
            "total_chunks": 2,
            "total_words": 10101,
            "chunking_strategy": "AgentChunker"
        }
    """
    # Verify authentication
    auth_header = request.headers.get("authorization")
    if not verify_api_key(auth_header):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Invalid or missing API key"}
        )

    try:
        # Parse request body
        body = await request.json()
        content_url = body.get("content_url")
        storage_id = body.get("storage_id")
        target_words = body.get("target_words", 5000)

        if not content_url or not storage_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Bad Request", "message": "Missing content_url or storage_id"}
            )

        print(f"\n{'='*80}")
        print(f"✂️  CHUNK STORY REQUEST")
        print(f"{'='*80}")
        print(f"Storage ID: {storage_id}")
        print(f"Content URL: {content_url}")
        print(f"Target words: {target_words}")

        # Initialize Supabase Storage
        storage = SupabaseStorage()

        # Chunk the story (always uses AgentChunker)
        result = chunk_story(
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

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                **result
            }
        )

    except Exception as e:
        print(f"\n❌ Chunking error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")

        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "message": str(e)}
        )


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("story-prep-secrets"),
        modal.Secret.from_name("supabase-secrets"),
    ],
    timeout=30,
)
@modal.web_endpoint(method="GET")
async def health_endpoint(request: Request):
    """
    Health check endpoint.

    GET /health

    Response:
        {
            "status": "healthy",
            "services": {
                "anthropic_api": "ok|error",
                "supabase_storage": "ok|error"
            }
        }
    """
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

    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "services": services
        }
    )


# Local testing entrypoint
@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.

    Run with: modal run modal-api/main.py
    """
    print("Modal API is ready to deploy!")
    print(f"App name: {APP_NAME}")
    print("\nTo deploy:")
    print(f"  modal deploy modal-api/main.py")
    print("\nEndpoints:")
    print("  POST /extract-content")
    print("  POST /chunk-story")
    print("  GET /health")

