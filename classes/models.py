"""
This file defines the database tables to be stored for classes.
"""

from django.conf import settings
from django.db import models

from curriculum.models import MicroSkill


# The class to handle the school class table
class SchoolClass(models.Model):

    # Attributes inside the school class table
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classes_taught",
        limit_choices_to={"role": "teacher"},
    )
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Properties of the table
    class Meta:
        ordering = ["name"]
        verbose_name_plural = "classes"

    # toString method that returns the name of the class
    def __str__(self):
        return self.name

    # A function to retrieve students currently in class
    @property
    def active_memberships(self):
        return self.memberships.filter(is_active=True)

    # A function to count the number of active students in the class
    @property
    def student_count(self):
        return self.active_memberships.count()


# The membership table that details which students are in which class
class Membership(models.Model):

    # Attributes of the table
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="memberships"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="class_memberships",
        limit_choices_to={"role": "student"},
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    restrictions_disabled = models.BooleanField(default=False)

    # Properties of the table
    class Meta:
        unique_together = ("school_class", "student")
        ordering = ["-joined_at"]

    # A function to return the string of the table
    def __str__(self):
        return f"{self.student} in {self.school_class}"


# The table that details the topics that a class can see
class TopicAvailability(models.Model):

    # Attributes of the table
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="topic_settings"
    )
    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.CASCADE, related_name="availability_settings"
    )
    is_available = models.BooleanField(default=True)

    # Properties of the table
    class Meta:
        unique_together = ("school_class", "micro_skill")

    # A function to return the string of the table
    def __str__(self):
        state = "available" if self.is_available else "hidden"
        return f"{self.micro_skill.title} · {state} in {self.school_class}"
