# apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Q
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    # list_display base (sin is_superuser); se agrega dinámicamente para superuser
    list_display = ("email", "full_name", "is_staff", "is_active")
    search_fields = ("email", "full_name")

    # ---- fieldsets base (se escogen dinámicamente) ----
    _FIELDSETS_SUPER = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("full_name",)}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    _FIELDSETS_STAFF = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("full_name",)}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff")},
        ),  # sin is_superuser ni permisos
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    _ADD_FIELDSETS_SUPER = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
    _ADD_FIELDSETS_STAFF = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff"),
            },
        ),
    )

    # ---------- util ----------
    def _all_field_names(self):
        return [f.name for f in self.model._meta.fields] + [
            m.name for m in self.model._meta.many_to_many
        ]

    # ---------- queryset/visibilidad de filas ----------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Staff ve staff y no-staff; oculta superusers
        return qs.filter(is_superuser=False)

    # ---------- columnas dinámicas ----------
    def get_list_display(self, request):
        if request.user.is_superuser:
            return ("email", "full_name", "is_staff", "is_superuser", "is_active")
        return super().get_list_display(request)

    # ---------- fieldsets dinámicos ----------
    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return self._FIELDSETS_SUPER if obj else self._ADD_FIELDSETS_SUPER
        return self._FIELDSETS_STAFF if obj else self._ADD_FIELDSETS_STAFF

    # ---------- permisos ----------
    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if not base:
            return False
        if request.user.is_superuser or obj is None:
            return True
        if obj.is_superuser:
            return False  # staff no ve superusers
        return True  # staff ve staff y no-staff

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base:
            return False
        if request.user.is_superuser or obj is None:
            return True
        if obj.is_superuser or obj.is_staff:
            return False  # staff no edita staff/superusers (incluido él mismo)
        return True

    def has_delete_permission(self, request, obj=None):
        base = super().has_delete_permission(request, obj)
        if not base:
            return False
        if request.user.is_superuser or obj is None:
            return True
        if obj.is_superuser or obj.is_staff:
            return False
        return True

    # ---------- form/readonly ----------
    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser:
            # Ocultar SIEMPRE campos de superuser/permiso a staff
            exclude = set(kwargs.get("exclude") or [])
            exclude.update({"is_superuser", "groups", "user_permissions"})
            # También ocultamos is_staff del formulario para staff (solo lectura)
            exclude.update({"is_staff"})
            kwargs["exclude"] = tuple(sorted(exclude))
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            ro += ["last_login", "date_joined"]
            # Nunca permitir tocar privilegios aunque se muestren en lista
            ro += ["is_superuser", "is_staff", "groups", "user_permissions"]
            if obj and (obj.is_staff or obj.is_superuser):
                # Ver staff/superusers solo en lectura total
                ro = sorted(set(ro + self._all_field_names()))
        return tuple(sorted(set(ro)))

    # ---------- guardado defensivo ----------
    def save_model(self, request, obj, form, change):
        # Anti-escalamiento: un staff no puede crear/elevar privilegios
        if not request.user.is_superuser:
            if change:
                original = User.objects.get(pk=obj.pk)
                obj.is_staff = original.is_staff
                obj.is_superuser = original.is_superuser
            else:
                obj.is_staff = False
                obj.is_superuser = False
        super().save_model(request, obj, form, change)
