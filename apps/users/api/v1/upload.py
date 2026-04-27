from dataclasses import asdict

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shared.cloudinary import (
    CloudinaryValidationError,
    delete_uploaded_asset,
    generate_upload_signature_for_folder,
    normalize_destroy_result,
    validate_cloudinary_asset,
)
from apps.users.cloudinary import CLIENT_AVATAR_FOLDER, CLIENT_AVATAR_PREFIXES


class ClientAvatarUploadSignatureView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename = request.data.get("filename")

        try:
            params = generate_upload_signature_for_folder(
                folder=CLIENT_AVATAR_FOLDER,
                resource_type="image",
                original_filename=filename,
            )
            return Response(asdict(params))
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ClientAvatarUploadCleanupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        assets = request.data.get("assets")
        if not isinstance(assets, list) or not assets:
            return Response(
                {"error": "assets must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                return Response(
                    {"error": f"assets[{index}] must be an object"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                ref = validate_cloudinary_asset(
                    reference={**asset, "resource_type": "image"},
                    allowed_prefixes=CLIENT_AVATAR_PREFIXES,
                )
            except CloudinaryValidationError as exc:
                return Response(
                    {"error": f"assets[{index}] invalid: {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                provider_result = delete_uploaded_asset(
                    public_id=ref.public_id,
                    resource_type="image",
                )
                item_status, raw_result = normalize_destroy_result(provider_result)
                results.append(
                    {
                        "public_id": ref.public_id,
                        "resource_type": "image",
                        "status": item_status,
                        "provider_result": raw_result,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "public_id": ref.public_id,
                        "resource_type": "image",
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
