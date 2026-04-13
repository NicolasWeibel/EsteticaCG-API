from __future__ import annotations

import posixpath
from dataclasses import dataclass

import cloudinary
import cloudinary.api
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from .normalize_cloudinary_assets import CANONICAL_FOLDERS


@dataclass(frozen=True)
class AssetFolderMismatch:
    model_label: str
    pk: object
    field_name: str
    public_id: str
    expected_public_id: str
    expected_asset_folder: str
    actual_asset_folder: str | None
    resource_type: str


class Command(BaseCommand):
    help = (
        "Audita y opcionalmente corrige el asset_folder visual de los assets de "
        "Cloudinary referenciados por la DB del entorno actual, sin cambiar su public_id."
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
            help="Solo informa inconsistencias, sin actualizar asset_folder.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Límite opcional de referencias a inspeccionar.",
        )
        parser.add_argument(
            "--model",
            action="append",
            default=[],
            help=(
                "Restringe a uno o más model labels, por ejemplo catalog.Journey o "
                "catalog.Category. Se puede repetir."
            ),
        )

    def handle(self, *args, **options):
        self._configure_cloudinary()
        prefix = self._resolve_prefix(options.get("prefix") or "")
        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 0)
        model_filter = {
            value.strip() for value in options.get("model") or [] if value.strip()
        }

        mismatches = self._collect_mismatches(prefix=prefix, model_filter=model_filter)
        if limit > 0:
            mismatches = mismatches[:limit]

        if not mismatches:
            self.stdout.write(
                self.style.SUCCESS(
                    "No se encontraron assets canónicos con asset_folder visual desalineado."
                )
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Assets con asset_folder visual desalineado: {len(mismatches)}"
            )
        )
        self._print_summary(mismatches)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no se hicieron cambios."))
            return

        updated = 0
        for item in mismatches:
            cloudinary.api.update(
                item.public_id,
                resource_type=item.resource_type,
                asset_folder=item.expected_asset_folder,
            )
            updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"[updated] {item.public_id} -> asset_folder={item.expected_asset_folder}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronización completa. Assets actualizados: {updated}."
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

    def _collect_mismatches(
        self,
        *,
        prefix: str,
        model_filter: set[str],
    ) -> list[AssetFolderMismatch]:
        mismatches: list[AssetFolderMismatch] = []

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
                target_folder = self._target_folder(model_label, field)
                if not target_folder:
                    continue

                expected_asset_folder = f"{prefix}/{target_folder}".strip("/")
                field_name = field.name
                rows = model._default_manager.exclude(
                    **{f"{field_name}__isnull": True}
                ).exclude(**{field_name: ""})

                for row in rows.values("pk", field_name):
                    public_id = (row.get(field_name) or "").strip().strip("/")
                    if not public_id.startswith(f"{prefix}/"):
                        continue

                    expected_public_id = self._build_expected_public_id(
                        public_id=public_id,
                        prefix=prefix,
                        target_folder=target_folder,
                    )
                    if public_id != expected_public_id:
                        continue

                    resource = self._get_resource(public_id, field)
                    actual_asset_folder = resource.get("asset_folder")
                    if actual_asset_folder == expected_asset_folder:
                        continue

                    mismatches.append(
                        AssetFolderMismatch(
                            model_label=model_label,
                            pk=row["pk"],
                            field_name=field_name,
                            public_id=public_id,
                            expected_public_id=expected_public_id,
                            expected_asset_folder=expected_asset_folder,
                            actual_asset_folder=actual_asset_folder,
                            resource_type=resource["resource_type"],
                        )
                    )

        mismatches.sort(
            key=lambda item: (
                item.model_label,
                item.field_name,
                str(item.pk),
                item.public_id,
            )
        )
        return mismatches

    def _target_folder(self, model_label: str, field: models.FileField) -> str | None:
        explicit = CANONICAL_FOLDERS.get((model_label, field.name))
        if explicit:
            return explicit.strip().strip("/")

        upload_to = getattr(field, "upload_to", "")
        if isinstance(upload_to, str) and upload_to.strip("/"):
            return upload_to.strip().strip("/")
        return None

    def _build_expected_public_id(
        self,
        *,
        public_id: str,
        prefix: str,
        target_folder: str,
    ) -> str:
        basename = posixpath.basename(public_id)
        if not basename:
            raise CommandError(
                f"No pude calcular basename para el public_id '{public_id}'."
            )
        return f"{prefix}/{target_folder}/{basename}".strip("/")

    def _get_resource(
        self,
        public_id: str,
        field: models.FileField,
    ) -> dict:
        resource_types = []
        if isinstance(field, models.ImageField):
            resource_types = ["image"]
        else:
            resource_types = ["image", "video"]

        tried: set[str] = set()
        for resource_type in resource_types:
            tried.add(resource_type)
            try:
                return cloudinary.api.resource(public_id, resource_type=resource_type)
            except cloudinary.api.NotFound:
                continue

        raise CommandError(
            f"No encontré el asset en Cloudinary: {public_id}. "
            f"Intenté resource_type={sorted(tried)}."
        )

    def _print_summary(self, mismatches: list[AssetFolderMismatch]) -> None:
        by_model_field: dict[tuple[str, str], int] = {}
        for item in mismatches:
            key = (item.model_label, item.field_name)
            by_model_field[key] = by_model_field.get(key, 0) + 1

        for (model_label, field_name), count in sorted(by_model_field.items()):
            self.stdout.write(f"- {model_label}.{field_name}: {count}")

        self.stdout.write("Ejemplos:")
        for item in mismatches[:15]:
            self.stdout.write(
                f"  {item.model_label}(pk={item.pk}).{item.field_name}: "
                f"{item.public_id} | asset_folder actual={item.actual_asset_folder or '<none>'} "
                f"-> esperado={item.expected_asset_folder}"
            )
