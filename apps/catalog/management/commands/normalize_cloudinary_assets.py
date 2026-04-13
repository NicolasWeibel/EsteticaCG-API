from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import Iterable

import cloudinary
import cloudinary.api
import cloudinary.uploader
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models

# Canonical folders actually enforced by the current direct-upload flow.
CANONICAL_FOLDERS: dict[tuple[str, str], str] = {
    ("catalog.Category", "image"): "catalog/categories",
    ("catalog.Objective", "image"): "catalog/filters/objectives",
    ("catalog.Treatment", "benefits_image"): "catalog/items/benefits",
    ("catalog.Treatment", "recommended_image"): "catalog/items/recommended",
    ("catalog.Combo", "benefits_image"): "catalog/items/benefits",
    ("catalog.Combo", "recommended_image"): "catalog/items/recommended",
    ("catalog.Journey", "benefits_image"): "catalog/journeys/benefits",
    ("catalog.Journey", "recommended_image"): "catalog/journeys/recommended",
    ("catalog.TreatmentMedia", "media"): "catalog/treatments",
    ("catalog.ComboMedia", "media"): "catalog/combos",
    ("catalog.JourneyMedia", "media"): "catalog/journeys",
    ("waxing.WaxingContent", "image"): "waxing/content",
    ("waxing.WaxingContent", "benefits_image"): "waxing/content",
    ("waxing.WaxingContent", "recommendations_image"): "waxing/content",
    ("waxing.Section", "image"): "waxing/sections",
    ("waxing.AreaCategory", "image"): "waxing/area_categories",
    ("waxing.Area", "image"): "waxing/areas",
    ("waxing.Pack", "image"): "waxing/packs",
}


@dataclass(frozen=True)
class AssetOccurrence:
    model: type[models.Model]
    model_label: str
    pk: object
    field_name: str
    old_public_id: str
    new_public_id: str
    guessed_resource_type: str | None


@dataclass
class GroupedAsset:
    old_public_id: str
    new_public_ids: set[str]
    guessed_resource_types: set[str]


class Command(BaseCommand):
    help = (
        "Normaliza todos los assets referenciados por la DB de staging para que "
        "queden bajo el prefijo de staging y dentro de su carpeta canónica. "
        "Copia/clona el asset en Cloudinary, actualiza la DB sin disparar signals "
        "de cleanup y opcionalmente elimina el asset viejo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="",
            help=(
                "Prefijo staging a normalizar. Por default usa "
                "settings.CLOUDINARY_STORAGE['PREFIX']."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué assets y filas cambiaría, sin copiar ni actualizar.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Límite opcional de referencias a procesar, útil para pruebas.",
        )
        parser.add_argument(
            "--skip-missing",
            action="store_true",
            help=(
                "Si un asset origen no existe en Cloudinary, lo omite y deja "
                "esa referencia sin tocar en la DB."
            ),
        )
        parser.add_argument(
            "--delete-source",
            action="store_true",
            help=(
                "Después de actualizar la DB, elimina los public_id viejos en "
                "Cloudinary. Por seguridad, el default es conservarlos."
            ),
        )
        parser.add_argument(
            "--model",
            action="append",
            default=[],
            help=(
                "Restringe a uno o más model labels, por ejemplo catalog.Category o "
                "catalog.TreatmentMedia. Se puede repetir."
            ),
        )

    def handle(self, *args, **options):
        self._configure_cloudinary()
        prefix = self._resolve_prefix(options.get("prefix") or "")
        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 0)
        skip_missing = bool(options.get("skip_missing"))
        delete_source = bool(options.get("delete_source"))
        model_filter = {
            value.strip() for value in options.get("model") or [] if value.strip()
        }

        occurrences = self._collect_occurrences(
            prefix=prefix, model_filter=model_filter
        )
        if limit > 0:
            occurrences = occurrences[:limit]

        if not occurrences:
            self.stdout.write(
                self.style.WARNING("No se encontraron referencias desnormalizadas.")
            )
            return

        grouped = self._group_assets(occurrences)

        self.stdout.write(
            self.style.NOTICE(
                f"Referencias a normalizar: {len(occurrences)} | "
                f"assets únicos origen: {len(grouped)}"
            )
        )
        self._print_occurrence_summary(occurrences)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no se hicieron cambios."))
            return

        copied_assets = 0
        reused_assets = 0
        skipped_missing_assets: set[str] = set()
        copied_pairs: set[tuple[str, str]] = set()

        for old_public_id, asset in grouped.items():
            try:
                resource_type = self._resolve_resource_type(old_public_id, asset)
            except CommandError:
                if not skip_missing:
                    raise
                skipped_missing_assets.add(old_public_id)
                self.stdout.write(
                    self.style.WARNING(
                        f"[missing] {old_public_id} no existe en Cloudinary; se omite."
                    )
                )
                continue

            source_meta = self._get_resource(
                old_public_id, asset.guessed_resource_types
            )
            source_url = source_meta.get("secure_url") or source_meta.get("url")
            if not source_url:
                raise CommandError(
                    f"No pude obtener una URL fuente para {old_public_id}."
                )

            for new_public_id in sorted(asset.new_public_ids):
                pair = (old_public_id, new_public_id)
                if self._resource_exists(new_public_id, resource_type):
                    reused_assets += 1
                    copied_pairs.add(pair)
                    self.stdout.write(
                        f"[exists] {new_public_id} ({resource_type}) ya existe; se reutiliza."
                    )
                    continue

                upload_kwargs = {
                    "public_id": new_public_id,
                    "resource_type": resource_type,
                    "overwrite": False,
                    "use_filename": False,
                    "unique_filename": False,
                }
                asset_folder = posixpath.dirname(new_public_id)
                if asset_folder:
                    upload_kwargs["asset_folder"] = asset_folder

                tags = source_meta.get("tags") or []
                if tags:
                    upload_kwargs["tags"] = tags

                custom_context = (source_meta.get("context") or {}).get("custom") or {}
                if custom_context:
                    upload_kwargs["context"] = custom_context

                cloudinary.uploader.upload(source_url, **upload_kwargs)
                copied_assets += 1
                copied_pairs.add(pair)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[copied] {old_public_id} -> {new_public_id} ({resource_type})"
                    )
                )

        updated_rows = 0
        for occurrence in occurrences:
            if occurrence.old_public_id in skipped_missing_assets:
                continue
            if (occurrence.old_public_id, occurrence.new_public_id) not in copied_pairs:
                continue
            updated_rows += occurrence.model._default_manager.filter(
                pk=occurrence.pk
            ).update(**{occurrence.field_name: occurrence.new_public_id})

        deleted_sources = 0
        if delete_source:
            for old_public_id, asset in grouped.items():
                if old_public_id in skipped_missing_assets:
                    continue
                try:
                    resource_type = self._resolve_resource_type(old_public_id, asset)
                    result = cloudinary.uploader.destroy(
                        old_public_id,
                        resource_type=resource_type,
                        invalidate=True,
                    )
                    if result.get("result") == "ok":
                        deleted_sources += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[deleted-source] {old_public_id} ({resource_type})"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[delete-source:{result.get('result', 'unknown')}] "
                                f"{old_public_id} ({resource_type})"
                            )
                        )
                except Exception as exc:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[delete-source:error] {old_public_id}: {exc}"
                        )
                    )

        skipped_occurrences = sum(
            1
            for occurrence in occurrences
            if occurrence.old_public_id in skipped_missing_assets
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Normalización completa. "
                f"Assets copiados: {copied_assets}. "
                f"Assets reutilizados: {reused_assets}. "
                f"Filas actualizadas: {updated_rows}. "
                f"Referencias omitidas: {skipped_occurrences}. "
                f"Sources eliminados: {deleted_sources}."
            )
        )

        if skipped_missing_assets:
            self.stdout.write(
                self.style.WARNING(
                    "Assets faltantes omitidos:\n- "
                    + "\n- ".join(sorted(skipped_missing_assets))
                )
            )

    def _configure_cloudinary(self) -> None:
        from django.conf import settings

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
            from django.conf import settings

            prefix = (
                (getattr(settings, "CLOUDINARY_STORAGE", {}).get("PREFIX", "") or "")
                .strip()
                .strip("/")
            )
        if not prefix:
            raise CommandError("No pude resolver el prefijo de staging.")
        return prefix

    def _collect_occurrences(
        self,
        *,
        prefix: str,
        model_filter: set[str],
    ) -> list[AssetOccurrence]:
        occurrences: list[AssetOccurrence] = []

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

                guessed_resource_type = self._guess_resource_type(model, field)
                field_name = field.name
                rows = model._default_manager.exclude(
                    **{f"{field_name}__isnull": True}
                ).exclude(**{field_name: ""})

                for row in rows.values("pk", field_name):
                    old_public_id = (row.get(field_name) or "").strip().strip("/")
                    if not old_public_id:
                        continue
                    new_public_id = self._build_target_public_id(
                        old_public_id=old_public_id,
                        prefix=prefix,
                        target_folder=target_folder,
                    )
                    if old_public_id == new_public_id:
                        continue
                    occurrences.append(
                        AssetOccurrence(
                            model=model,
                            model_label=model_label,
                            pk=row["pk"],
                            field_name=field_name,
                            old_public_id=old_public_id,
                            new_public_id=new_public_id,
                            guessed_resource_type=guessed_resource_type,
                        )
                    )

        occurrences.sort(
            key=lambda item: (
                item.model_label,
                item.field_name,
                str(item.pk),
                item.old_public_id,
                item.new_public_id,
            )
        )
        return occurrences

    def _target_folder(self, model_label: str, field: models.FileField) -> str | None:
        explicit = CANONICAL_FOLDERS.get((model_label, field.name))
        if explicit:
            return explicit.strip().strip("/")

        upload_to = getattr(field, "upload_to", "")
        if isinstance(upload_to, str) and upload_to.strip("/"):
            return upload_to.strip().strip("/")
        return None

    def _build_target_public_id(
        self,
        *,
        old_public_id: str,
        prefix: str,
        target_folder: str,
    ) -> str:
        basename = posixpath.basename(old_public_id)
        if not basename:
            raise CommandError(
                f"No pude calcular basename para el public_id '{old_public_id}'."
            )
        return f"{prefix}/{target_folder}/{basename}".strip("/")

    def _guess_resource_type(
        self,
        model: type[models.Model],
        field: models.FileField,
    ) -> str | None:
        if isinstance(field, models.ImageField):
            return "image"
        if field.name == "media":
            return None
        return None

    def _group_assets(
        self,
        occurrences: Iterable[AssetOccurrence],
    ) -> dict[str, GroupedAsset]:
        grouped: dict[str, GroupedAsset] = {}
        for occurrence in occurrences:
            current = grouped.get(occurrence.old_public_id)
            if current is None:
                grouped[occurrence.old_public_id] = GroupedAsset(
                    old_public_id=occurrence.old_public_id,
                    new_public_ids={occurrence.new_public_id},
                    guessed_resource_types=set(
                        [occurrence.guessed_resource_type]
                        if occurrence.guessed_resource_type
                        else []
                    ),
                )
                continue
            current.new_public_ids.add(occurrence.new_public_id)
            if occurrence.guessed_resource_type:
                current.guessed_resource_types.add(occurrence.guessed_resource_type)
        return grouped

    def _resolve_resource_type(self, public_id: str, asset: GroupedAsset) -> str:
        metadata = self._get_resource(public_id, asset.guessed_resource_types)
        resource_type = metadata.get("resource_type")
        if resource_type not in {"image", "video"}:
            raise CommandError(f"No pude resolver resource_type para {public_id}.")
        return resource_type

    def _get_resource(
        self,
        public_id: str,
        guessed_resource_types: set[str],
    ) -> dict:
        types_to_try = [*guessed_resource_types, "image", "video"]
        tried: set[str] = set()

        for resource_type in types_to_try:
            if not resource_type or resource_type in tried:
                continue
            tried.add(resource_type)
            try:
                return cloudinary.api.resource(public_id, resource_type=resource_type)
            except cloudinary.api.NotFound:
                continue

        raise CommandError(
            f"No encontré el asset en Cloudinary: {public_id}. "
            f"Intenté resource_type={sorted(tried)}."
        )

    def _resource_exists(self, public_id: str, resource_type: str) -> bool:
        try:
            cloudinary.api.resource(public_id, resource_type=resource_type)
            return True
        except cloudinary.api.NotFound:
            return False

    def _print_occurrence_summary(self, occurrences: list[AssetOccurrence]) -> None:
        by_model_field: dict[tuple[str, str], int] = {}
        for item in occurrences:
            key = (item.model_label, item.field_name)
            by_model_field[key] = by_model_field.get(key, 0) + 1

        for (model_label, field_name), count in sorted(by_model_field.items()):
            self.stdout.write(f"- {model_label}.{field_name}: {count}")

        self.stdout.write("Ejemplos:")
        for item in occurrences[:15]:
            self.stdout.write(
                f"  {item.model_label}(pk={item.pk}).{item.field_name}: "
                f"{item.old_public_id} -> {item.new_public_id}"
            )
