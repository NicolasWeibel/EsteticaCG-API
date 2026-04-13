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


@dataclass(frozen=True)
class AssetOccurrence:
    model: type[models.Model]
    model_label: str
    pk: object
    field_name: str
    old_public_id: str
    new_public_id: str
    guessed_resource_type: str | None


class Command(BaseCommand):
    help = (
        "Clona assets de Cloudinary referenciados por la DB desde un prefijo a otro "
        "y actualiza los public_id sin disparar signals de limpieza."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-prefix",
            required=True,
            help="Prefijo origen, por ejemplo: estetica-staging",
        )
        parser.add_argument(
            "--to-prefix",
            required=True,
            help="Prefijo destino, por ejemplo: estetica-production",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué assets y filas cambiaría, sin copiar ni actualizar.",
        )
        parser.add_argument(
            "--skip-upload",
            action="store_true",
            help=(
                "No copia assets en Cloudinary; solo actualiza la DB. "
                "Úsalo solo si ya clonaste los assets por otro medio."
            ),
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

    def handle(self, *args, **options):
        source_prefix = self._normalize_prefix(options["from_prefix"])
        target_prefix = self._normalize_prefix(options["to_prefix"])
        dry_run = options["dry_run"]
        skip_upload = options["skip_upload"]
        skip_missing = options["skip_missing"]
        limit = int(options["limit"] or 0)

        if source_prefix == target_prefix:
            raise CommandError("El prefijo origen y destino no pueden ser iguales.")

        self._configure_cloudinary()

        occurrences = self._collect_occurrences(source_prefix, target_prefix)
        if limit > 0:
            occurrences = occurrences[:limit]

        if not occurrences:
            self.stdout.write(
                self.style.WARNING(
                    f"No se encontraron referencias con prefijo '{source_prefix}/'."
                )
            )
            return

        unique_assets = self._group_assets(occurrences)

        self.stdout.write(
            self.style.NOTICE(
                f"Referencias encontradas: {len(occurrences)} | "
                f"assets únicos: {len(unique_assets)}"
            )
        )
        self._print_occurrence_summary(occurrences)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no se hicieron cambios."))
            return

        cloned_assets = 0
        reused_assets = 0
        skipped_missing_assets: set[str] = set()

        for old_public_id, asset in unique_assets.items():
            new_public_id = asset.new_public_id
            try:
                resource_type = self._resolve_resource_type(asset)
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

            if skip_upload:
                self.stdout.write(
                    f"[skip-upload] {old_public_id} -> {new_public_id} ({resource_type})"
                )
                continue

            if self._resource_exists(new_public_id, resource_type):
                reused_assets += 1
                self.stdout.write(
                    f"[exists] {new_public_id} ({resource_type}) ya existe; se reutiliza."
                )
                continue

            source_meta = self._get_resource(old_public_id, asset.guessed_resource_types)
            source_url = source_meta.get("secure_url") or source_meta.get("url")
            if not source_url:
                raise CommandError(
                    f"No pude obtener una URL fuente para {old_public_id}."
                )

            upload_kwargs = {
                "public_id": new_public_id,
                "resource_type": resource_type,
                "overwrite": False,
                "use_filename": False,
                "unique_filename": False,
            }
            asset_folder = posixpath.dirname(new_public_id)
            if asset_folder:
                # Hace más probable que Cloudinary UI muestre el asset bajo la carpeta correcta.
                upload_kwargs["asset_folder"] = asset_folder

            tags = source_meta.get("tags") or []
            if tags:
                upload_kwargs["tags"] = tags

            custom_context = (source_meta.get("context") or {}).get("custom") or {}
            if custom_context:
                upload_kwargs["context"] = custom_context

            cloudinary.uploader.upload(source_url, **upload_kwargs)
            cloned_assets += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"[cloned] {old_public_id} -> {new_public_id} ({resource_type})"
                )
            )

        updated_rows = 0
        for occurrence in occurrences:
            if occurrence.old_public_id in skipped_missing_assets:
                continue
            updated_rows += occurrence.model._default_manager.filter(
                pk=occurrence.pk
            ).update(**{occurrence.field_name: occurrence.new_public_id})

        skipped_occurrences = sum(
            1 for occurrence in occurrences if occurrence.old_public_id in skipped_missing_assets
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Migración completa. "
                f"Assets clonados: {cloned_assets}. "
                f"Assets reutilizados: {reused_assets}. "
                f"Filas actualizadas: {updated_rows}. "
                f"Referencias omitidas: {skipped_occurrences}."
            )
        )
        if skipped_missing_assets:
            self.stdout.write(
                self.style.WARNING(
                    "Assets faltantes omitidos:\n- "
                    + "\n- ".join(sorted(skipped_missing_assets))
                )
            )

    def _normalize_prefix(self, value: str) -> str:
        normalized = (value or "").strip().strip("/")
        if not normalized:
            raise CommandError("El prefijo no puede estar vacío.")
        return normalized

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

    def _collect_occurrences(
        self, source_prefix: str, target_prefix: str
    ) -> list[AssetOccurrence]:
        occurrences: list[AssetOccurrence] = []
        prefix_lookup = f"{source_prefix}/"

        for model in apps.get_models():
            if not model.__module__.startswith("apps."):
                continue

            file_fields = [
                field
                for field in model._meta.get_fields()
                if isinstance(field, models.FileField) and getattr(field, "concrete", False)
            ]
            if not file_fields:
                continue

            for field in file_fields:
                guessed_resource_type = self._guess_resource_type(model, field)
                field_name = field.name
                rows = model._default_manager.filter(
                    **{f"{field_name}__startswith": prefix_lookup}
                ).values_list("pk", field_name)

                for pk, old_public_id in rows:
                    if not old_public_id:
                        continue
                    occurrences.append(
                        AssetOccurrence(
                            model=model,
                            model_label=model._meta.label,
                            pk=pk,
                            field_name=field_name,
                            old_public_id=old_public_id,
                            new_public_id=self._replace_prefix(
                                old_public_id, source_prefix, target_prefix
                            ),
                            guessed_resource_type=guessed_resource_type,
                        )
                    )

        occurrences.sort(
            key=lambda item: (
                item.model_label,
                item.field_name,
                str(item.pk),
                item.old_public_id,
            )
        )
        return occurrences

    def _guess_resource_type(
        self, model: type[models.Model], field: models.FileField
    ) -> str | None:
        if isinstance(field, models.ImageField):
            return "image"

        try:
            model._meta.get_field("media_type")
        except Exception:
            return None

        if field.name == "media":
            return None
        return None

    def _replace_prefix(
        self, public_id: str, source_prefix: str, target_prefix: str
    ) -> str:
        if public_id == source_prefix:
            return target_prefix
        if public_id.startswith(f"{source_prefix}/"):
            return f"{target_prefix}/{public_id[len(source_prefix) + 1:]}"
        raise CommandError(
            f"El public_id '{public_id}' no pertenece al prefijo '{source_prefix}'."
        )

    def _group_assets(
        self, occurrences: Iterable[AssetOccurrence]
    ) -> dict[str, "_GroupedAsset"]:
        grouped: dict[str, _GroupedAsset] = {}
        for occurrence in occurrences:
            current = grouped.get(occurrence.old_public_id)
            if current is None:
                grouped[occurrence.old_public_id] = _GroupedAsset(
                    old_public_id=occurrence.old_public_id,
                    new_public_id=occurrence.new_public_id,
                    guessed_resource_types=set(
                        [occurrence.guessed_resource_type]
                        if occurrence.guessed_resource_type
                        else []
                    ),
                )
                continue
            current.guessed_resource_types.update(
                [occurrence.guessed_resource_type] if occurrence.guessed_resource_type else []
            )
        return grouped

    def _resolve_resource_type(self, asset: "_GroupedAsset") -> str:
        metadata = self._get_resource(asset.old_public_id, asset.guessed_resource_types)
        resource_type = metadata.get("resource_type")
        if resource_type not in {"image", "video"}:
            raise CommandError(
                f"No pude resolver resource_type para {asset.old_public_id}."
            )
        return resource_type

    def _get_resource(
        self, public_id: str, guessed_resource_types: set[str]
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

        sample = occurrences[:10]
        self.stdout.write("Ejemplos:")
        for item in sample:
            self.stdout.write(
                f"  {item.model_label}(pk={item.pk}).{item.field_name}: "
                f"{item.old_public_id} -> {item.new_public_id}"
            )


@dataclass
class _GroupedAsset:
    old_public_id: str
    new_public_id: str
    guessed_resource_types: set[str]
