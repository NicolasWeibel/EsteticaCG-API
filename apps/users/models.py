# apps/users/models.py
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email requerido")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        # Por qué: aunque uses OTP/Google, permite setear password si lo necesitas
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser requiere is_staff=True y is_superuser=True")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Client(models.Model):
    class Gender(models.TextChoices):
        FEMALE = "female", "Femenino"
        MALE = "male", "Masculino"
        OTHER = "other", "Otro"

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="client"
    )
    email = models.EmailField(db_index=True)
    dni = models.CharField(max_length=64, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    gender = models.CharField(
        max_length=16, choices=Gender.choices, null=True, blank=True
    )
    phone_number = models.CharField(max_length=50, blank=True)
    google_avatar_url = models.URLField(blank=True)
    custom_avatar = models.ImageField(
        upload_to="clients/avatars/", blank=True, null=True
    )
    birth_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_booking_date = models.DateTimeField(null=True, blank=True)
    bookings_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        label = " ".join(part for part in [self.first_name, self.last_name] if part)
        return label or self.email
