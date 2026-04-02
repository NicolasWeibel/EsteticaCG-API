"""
Upload signing view for direct Cloudinary uploads.

This endpoint provides signed upload parameters that allow the frontend
to upload files directly to Cloudinary, bypassing Django/Cloud Run entirely.
This solves the 413 Content Too Large error for large files.
"""

from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shared.cloudinary import (
    delete_uploaded_asset,
    generate_upload_signature,
    ALLOWED_FOLDERS,
    get_allowed_prefixes_for_context,
    normalize_destroy_result,
    validate_upload_context,
    validate_cloudinary_asset,
    CloudinaryValidationError,
)


class UploadSignatureView(APIView):
    """
    Generate signed upload parameters for direct Cloudinary upload.

    POST /api/v1/catalog/upload/sign/
    {
        "context": "catalog_treatment_media",  # Required
        "resource_type": "auto",                # Optional: "image", "video", "auto"
        "filename": "my-video.mp4"              # Optional: original filename
    }

    Response:
    {
        "signature": "...",
        "timestamp": 1234567890,
        "cloud_name": "...",
        "api_key": "...",
        "folder": "...",
        "public_id": "...",              # Upload param for Cloudinary
        "final_public_id": "...",        # Persist this or use upload response public_id
        "resource_type": "...",
        "allowed_formats": [...],
        "max_file_size": 104857600,
        "upload_url": "https://api.cloudinary.com/v1_1/.../upload"
    }
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        context = request.data.get("context")
        resource_type = request.data.get("resource_type", "auto")
        filename = request.data.get("filename")

        try:
            context = validate_upload_context(context)
            params = generate_upload_signature(
                context=context,
                resource_type=resource_type,
                original_filename=filename,
            )
            return Response(asdict(params))
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UploadContextsView(APIView):
    """
    List available upload contexts.

    GET /api/v1/catalog/upload/contexts/

    Response:
    {
        "contexts": {
            "catalog_treatment_media": "catalog/treatments",
            ...
        }
    }
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"contexts": ALLOWED_FOLDERS})


class UploadCleanupView(APIView):
    """
    Cleanup previously uploaded Cloudinary assets that were never persisted.

    POST /api/v1/catalog/upload/cleanup/
    {
        "context": "catalog_treatment_media",
        "assets": [
            {"public_id": "...", "resource_type": "image"},
            {"public_id": "...", "resource_type": "video"}
        ]
    }
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        context = request.data.get("context")
        assets = request.data.get("assets")

        try:
            context = validate_upload_context(context)
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(assets, list) or not assets:
            return Response(
                {"error": "assets must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_prefixes = get_allowed_prefixes_for_context(context)
        results = []

        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                return Response(
                    {"error": f"assets[{index}] must be an object"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not asset.get("public_id") and not asset.get("url"):
                return Response(
                    {
                        "error": (
                            f"assets[{index}] invalid: Asset reference must include "
                            "'public_id' or 'url'"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            resource_type = asset.get("resource_type")
            if resource_type not in ("image", "video"):
                return Response(
                    {
                        "error": (
                            f"assets[{index}] must include "
                            "'resource_type' = 'image' or 'video'"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                ref = validate_cloudinary_asset(
                    reference=asset,
                    allowed_prefixes=allowed_prefixes,
                )
            except CloudinaryValidationError as exc:
                return Response(
                    {"error": f"assets[{index}] invalid: {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                provider_result = delete_uploaded_asset(
                    public_id=ref.public_id,
                    resource_type=ref.resource_type,
                )
                item_status, raw_result = normalize_destroy_result(provider_result)
                results.append(
                    {
                        "public_id": ref.public_id,
                        "resource_type": ref.resource_type,
                        "status": item_status,
                        "provider_result": raw_result,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "public_id": ref.public_id,
                        "resource_type": ref.resource_type,
                        "status": "failed",
                        "provider_result": "error",
                        "error": str(exc),
                    }
                )

        deleted_count = sum(1 for item in results if item["status"] == "deleted")
        not_found_count = sum(1 for item in results if item["status"] == "not_found")
        failed_count = sum(1 for item in results if item["status"] == "failed")

        return Response(
            {
                "ok": failed_count == 0,
                "results": results,
                "deleted_count": deleted_count,
                "not_found_count": not_found_count,
                "failed_count": failed_count,
            }
        )
