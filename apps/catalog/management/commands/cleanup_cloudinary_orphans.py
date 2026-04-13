from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import islice

import cloudinary
import cloudinary.api
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models


@dataclass(frozen=True)
class CloudinaryAsset:
    public_id: str
    resource_type: str
    asset_id: str | None
    asset_folder: str | None


class Command(BaseCommand):
    help = (
        "Encuentra assets de Cloudinary bajo el prefijo del entorno actual que no "
        "están referenciados por ningún FileField/ImageField de la DB y, opcionalmente, los elimina."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="",
            help=(
                "Prefijo a inspeccionar. Por default usa "
                "settings.CLOUDINARY_STORAGE['PREFIX']."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo informa huérfanos; no elimina nada.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Elimina los assets huérfanos encontrados.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Límite opcional de huérfanos a procesar.",
        )
        parser.add_argument(
            "--model",
            action="append",
            default=[],
            help=(
                "Restringe las referencias consideradas a uno o más model labels, "
                "por ejemplo catalog.Journey o waxing.Pack. Se puede repetir."
            ),
        )
        parser.add_argument(
            "--invalidate",
            action="store_true",
            help="Pide invalidación de CDN al eliminar assets.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        delete = bool(options.get("delete"))
        if dry_run and delete:
            raise CommandError("Usa --dry-run o --delete, no ambos a la vez.")
        if not dry_run and not delete:
            dry_run = True

        self._configure_cloudinary()
        prefix = self._resolve_prefix(options.get("prefix") or "")
        limit = int(options.get("limit") or 0)
        invalidate = bool(options.get("invalidate"))
        model_filter = {
            value.strip() for value in options.get("model") or [] if value.strip()
        }

        referenced_ids = self._collect_referenced_public_ids(prefix, model_filter)
        assets = self._list_assets(prefix)
        orphaned = [asset for asset in assets if asset.public_id not in referenced_ids]

        if limit > 0:
            orphaned = orphaned[:limit]

        self.stdout.write(
            self.style.NOTICE(
                f"Referencias DB: {len(referenced_ids)} | Assets Cloudinary bajo '{prefix}/': {len(assets)} | Huérfanos: {len(orphaned)}"
            )
        )
        self._print_summary(orphaned)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no se eliminaron assets."))
            return

        deleted = 0
        failed = 0

        for resource_type, public_ids in self._group_by_resource_type(orphaned).items():
            for batch in self._batched(public_ids, 100):
                result = cloudinary.api.delete_resources(
                    batch,
                    resource_type=resource_type,
                    invalidate=invalidate,
                )
                deleted_map = result.get("deleted", {}) or {}
                for public_id in batch:
                    status = deleted_map.get(public_id, "unknown")
                    if status == "deleted":
                        deleted += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"[deleted] {public_id} ({resource_type})")
                        )
                    else:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"[delete:{status}] {public_id} ({resource_type})"
                            )
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Limpieza completa. Assets eliminados: {deleted}. Fallidos/no eliminados: {failed}."
            )
        )

    def _configure_cloudinary(self) -> None:
        config = getattr(settings, "CLOUDINARY_STORAGE", {})
        cloud_name = config.get("CLOUD_NAME", "")
        api_key = config.get("API_KEY", "")
        api_secret = config.get("API_SECRET", "")

        if not all([cloud_name, api_key, api_secret]):
            raise CommandError(
                "Falta configuración de Cloudinary en CLOUDINARY_STORAGE."
            )

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
        )

    def _resolve_prefix(self, value: str) -> str:
        if value:
            prefix = value.strip().strip("/")
        else:
            prefix = (
                (getattr(settings, "CLOUDINARY_STORAGE", {}).get("PREFIX", "") or "")
                .strip()
                .strip("/")
            )
        if not prefix:
            raise CommandError("No pude resolver el prefijo configurado.")
        return prefix

    def _collect_referenced_public_ids(
        self,
        prefix: str,
        model_filter: set[str],
    ) -> set[str]:
        referenced: set[str] = set()

        for model in apps.get_models():
            if not model.__module__.startswith("apps."):
                continue
            model_label = model._meta.label
            if model_filter and model_label not in model_filter:
                continue

            file_fields = [
                field
                for field in model._meta.get_fields()
                if isinstance(field, models.FileField)
                and getattr(field, "concrete", False)
            ]
            if not file_fields:
                continue

            for field in file_fields:
                field_name = field.name
                rows = model._default_manager.exclude(
                    **{f"{field_name}__isnull": True}
                ).exclude(**{field_name: ""})
                for value in rows.values_list(field_name, flat=True):
                    public_id = (value or "").strip().strip("/")
                    if public_id.startswith(f"{prefix}/"):
                        referenced.add(public_id)

        return referenced

    def _list_assets(self, prefix: str) -> list[CloudinaryAsset]:
        assets: list[CloudinaryAsset] = []
        for resource_type in ("image", "video"):
            next_cursor: str | None = None
            while True:
                result = cloudinary.api.resources(
                    type="upload",
                    prefix=prefix,
                    resource_type=resource_type,
                    max_results=500,
                    next_cursor=next_cursor,
                )
                for resource in result.get("resources", []) or []:
                    public_id = (resource.get("public_id") or "").strip().strip("/")
                    if not public_id.startswith(f"{prefix}/"):
                        continue
                    assets.append(
                        CloudinaryAsset(
                            public_id=public_id,
                            resource_type=resource_type,
                            asset_id=resource.get("asset_id"),
                            asset_folder=resource.get("asset_folder"),
                        )
                    )
                next_cursor = result.get("next_cursor")
                if not next_cursor:
                    break
        return assets

    def _group_by_resource_type(
        self,
        assets: list[CloudinaryAsset],
    ) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for asset in assets:
            grouped[asset.resource_type].append(asset.public_id)
        return grouped

    def _batched(self, values: list[str], size: int):
        iterator = iter(values)
        while batch := list(islice(iterator, size)):
            yield batch

    def _print_summary(self, orphaned: list[CloudinaryAsset]) -> None:
        if not orphaned:
            self.stdout.write(self.style.SUCCESS("No se encontraron huérfanos."))
            return

        by_resource_type: dict[str, int] = defaultdict(int)
        for asset in orphaned:
            by_resource_type[asset.resource_type] += 1

        for resource_type, count in sorted(by_resource_type.items()):
            self.stdout.write(f"- {resource_type}: {count}")

        self.stdout.write("Ejemplos:")
        for asset in orphaned[:20]:
            self.stdout.write(
                f"  {asset.public_id} ({asset.resource_type}) | asset_folder={asset.asset_folder or '<none>'}"
            )
