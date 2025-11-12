# apps/catalog/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import NotFound


class IsAdminOrReadOnly(BasePermission):
    """
    Permite solo lectura a cualquiera,
    y escritura solo a usuarios staff/admin.
    """

    def has_permission(self, request, view):
        # Métodos de lectura (GET, HEAD, OPTIONS) → permitidos a todos
        if request.method in SAFE_METHODS:
            return True
        # Métodos de escritura → solo admin
        return request.user and request.user.is_staff


class IsAdminOnly(BasePermission):
    """
    Permite el acceso solo a usuarios con is_staff=True (admin del panel).
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsAdminOrNotFound(BasePermission):
    """
    Solo permite acceso a administradores.
    Usuarios no admin reciben 404 como si el recurso no existiera.
    """

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_staff:
            return True
        raise NotFound()
