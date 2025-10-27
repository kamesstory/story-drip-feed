"""
Modal API for Story Processing

Stateless HTTP API service for content extraction and story chunking.
Uses Supabase Storage for all file operations.
"""

import modal
import os

# Environment detection (use APP_ENV instead of MODAL_ENVIRONMENT to avoid conflicts)
IS_DEV = os.environ.get("APP_ENV", "dev") != "prod"
APP_NAME = "nighttime-story-prep-api-dev" if IS_DEV else "nighttime-story-prep-api"

# Environment-specific secrets
STORY_PREP_SECRET = "story-prep-secrets-dev" if IS_DEV else "story-prep-secrets-prod"
SUPABASE_SECRET = "supabase-secrets-dev" if IS_DEV else "supabase-secrets-prod"

print(f"🚀 Running Modal API in {'DEVELOPMENT' if IS_DEV else 'PRODUCTION'} mode")
print(f"   App: {APP_NAME}")
print(f"   Story Prep Secret: {STORY_PREP_SECRET}")
print(f"   Supabase Secret: {SUPABASE_SECRET}")

# Create Modal app
app = modal.App(APP_NAME)

# Define image with dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
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
    .add_local_file("src/supabase_storage.py", "/root/src/supabase_storage.py")
    .add_local_file("src/content_extraction_agent.py", "/root/src/content_extraction_agent.py")
    .add_local_file("src/chunker.py", "/root/src/chunker.py")
    .add_local_file("src/email_parser.py", "/root/src/email_parser.py")
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name(STORY_PREP_SECRET),
        modal.Secret.from_name(SUPABASE_SECRET),
    ],
    timeout=900,
)
@modal.asgi_app()
def fastapi_app():
    """Create and return the FastAPI app."""
    from fastapi import FastAPI, Request, HTTPException, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.responses import JSONResponse
    import traceback
    from src.supabase_storage import SupabaseStorage
    from src.content_extraction_agent import extract_content_async
    from src.chunker import chunk_story

    web_app = FastAPI(title="Nighttime Story Prep API")
    security = HTTPBearer()

    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
        """Verify the bearer token matches MODAL_API_KEY."""
        expected_key = os.environ.get("MODAL_API_KEY")
        if not expected_key:
            # If no key is configured, allow all requests (dev mode)
            print("⚠️  Warning: MODAL_API_KEY not set, allowing request", flush=True)
            return True
        
        if credentials.credentials != expected_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        return True

    @web_app.get("/health")
    async def health_endpoint():
        """Health check endpoint."""
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

        print(f"🏥 Health check: {overall_status}", flush=True)
        for service, status in services.items():
            print(f"   {service}: {status}", flush=True)

        return {
            "status": overall_status,
            "services": services
        }

    @web_app.post("/extract-content")
    async def extract_content_endpoint(request: Request, authenticated: bool = Depends(verify_token)):
        """Extract content from email data and store in Supabase."""
        try:
            body = await request.json()
            email_data = body.get("email_data")
            storage_id = body.get("storage_id")

            print(f"\n{'='*80}", flush=True)
            print(f"📥 EXTRACT CONTENT REQUEST", flush=True)
            print(f"{'='*80}", flush=True)
            print(f"Storage ID: {storage_id}", flush=True)
            print(f"Subject: {email_data.get('subject', 'N/A') if email_data else 'N/A'}", flush=True)
            print(f"From: {email_data.get('from', 'N/A') if email_data else 'N/A'}", flush=True)

            if not email_data or not storage_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Bad Request",
                        "message": "Missing email_data or storage_id"
                    }
                )

            storage = SupabaseStorage()
            result = await extract_content_async(email_data, storage_id, storage)

            print(f"\n✅ Content extraction successful", flush=True)
            print(f"   Content URL: {result['content_url']}", flush=True)
            print(f"   Title: {result['metadata'].get('title')}", flush=True)
            print(f"   Word count: {result['metadata'].get('word_count')}", flush=True)
            print(f"{'='*80}\n", flush=True)

            return {
                "status": "success",
                "content_url": result["content_url"],
                "metadata": result["metadata"]
            }

        except Exception as e:
            print(f"\n❌ Content extraction error: {e}", flush=True)
            traceback.print_exc()
            print(f"{'='*80}\n", flush=True)

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": str(e)
                }
            )

    @web_app.post("/chunk-story")
    async def chunk_story_endpoint(request: Request, authenticated: bool = Depends(verify_token)):
        """Chunk story content from Supabase Storage."""
        try:
            body = await request.json()
            content_url = body.get("content_url")
            storage_id = body.get("storage_id")
            target_words = body.get("target_words", 5000)

            print(f"\n{'='*80}", flush=True)
            print(f"✂️  CHUNK STORY REQUEST", flush=True)
            print(f"{'='*80}", flush=True)
            print(f"Storage ID: {storage_id}", flush=True)
            print(f"Content URL: {content_url}", flush=True)
            print(f"Target words: {target_words}", flush=True)

            if not content_url or not storage_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Bad Request",
                        "message": "Missing content_url or storage_id"
                    }
                )

            storage = SupabaseStorage()
            result = await chunk_story(
                content_url=content_url,
                storage_id=storage_id,
                target_words=target_words,
                storage=storage
            )

            print(f"\n✅ Chunking successful", flush=True)
            print(f"   Total chunks: {result['total_chunks']}", flush=True)
            print(f"   Total words: {result['total_words']}", flush=True)
            print(f"   Strategy used: {result['chunking_strategy']}", flush=True)
            print(f"{'='*80}\n", flush=True)

            return {
                "status": "success",
                **result
            }

        except Exception as e:
            print(f"\n❌ Chunking error: {e}", flush=True)
            traceback.print_exc()
            print(f"{'='*80}\n", flush=True)

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": str(e)
                }
            )

    return web_app


# Local testing entrypoint
@app.local_entrypoint()
def main():
    """Local testing entrypoint."""
    print("Modal API is ready to deploy!")
    print(f"App name: {APP_NAME}")
    print("\nTo deploy:")
    print(f"  modal deploy modal-api/main.py")
    print("\nEndpoints:")
    print("  GET /health")
    print("  POST /extract-content")
    print("  POST /chunk-story")
