"""
This file defines configurations related to the User object.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# A class to handle user creation
class UserManager(BaseUserManager):

    # If a migration creates users, this class is called
    use_in_migrations = True

    # A private function to create users
    def _create_user(self, email, password, **extra_fields):

        # Raise error if email is not provided
        if not email:
            raise ValueError("An email address is required.")

        # Normalize the email address (convert domains to lowercase)
        email = self.normalize_email(email)

        # Set the email and password for the user and save to database
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # A function to create a regular user account (student and teacher)
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    # A function to create a superuser account
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.TEACHER)

        # Additional check in case if any configuration is altered
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# A class to represent users
class User(AbstractUser):

    # A class to represent the roles of the user
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"

    # Remove the default username column
    username = None

    # The details to be extracted from forms
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.STUDENT
    )

    # Tell Django that the identifier is email, and admin does not require additional verification
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    # Attach the user manager class (to create user later)
    objects = UserManager()

    # Sort by names and email in default
    class Meta:
        ordering = ["full_name", "email"]

    # A function to print own details
    def __str__(self):
        return self.full_name or self.email

    # A function that determines whether the user is a student
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    # A function that determines whether the user is a teacher
    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    # A function to retrieve the user's first name (for main dashboard)
    @property
    def display_name(self):
        if self.full_name:
            return self.full_name.split()[0]
        return self.email.split("@")[0]
