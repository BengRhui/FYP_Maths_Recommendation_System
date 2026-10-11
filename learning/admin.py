"""
This file adds the components in the learning app to Django's admin site.
"""

from django.contrib import admin

from .models import (
    Attempt,
    MasterySnapshot,
    PracticeSession,
    SkillMastery,
    StudentProfile,
)


# The class that represents the student profile page
@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ["student", "total_attempts", "total_correct", "correct_streak", "last_attempt_at"]
    search_fields = ["student__email", "student__full_name"]


# The class that represents the skill mastery page
# Each student has their own mastery level for each skill
@admin.register(SkillMastery)
class SkillMasteryAdmin(admin.ModelAdmin):
    list_display = ["student", "micro_skill", "bkt_mastery", "attempts", "correct", "last_attempt_at"]
    list_filter = ["micro_skill__form_level", "micro_skill"]
    search_fields = ["student__email"]


# The class that represents the student practice sessions (the set of questions)
@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ["student", "micro_skill", "kind", "score", "total_questions", "is_complete", "created_at"]
    list_filter = ["kind", "is_complete"]


# The class that represents the individual question attempts from students
@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["student", "question", "micro_skill", "is_correct", "created_at"]
    list_filter = ["is_correct", "micro_skill"]
    search_fields = ["student__email"]


# The class that represents the mastery snapshot page (how each student's average mastery change)
@admin.register(MasterySnapshot)
class MasterySnapshotAdmin(admin.ModelAdmin):
    list_display = ["student", "overall_mastery", "recorded_at"]
