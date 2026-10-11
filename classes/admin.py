"""
This file adds class configurations to the Django admin site.
"""

from django.contrib import admin

from .models import Membership, SchoolClass, TopicAvailability

# The class to add and remove students inside a class
class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["student"]


# The class to show class details
@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ["name", "teacher", "student_count", "is_active"]
    search_fields = ["name"]
    inlines = [MembershipInline]


# The class to show students inside each class
@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["student", "school_class", "joined_at", "is_active"]
    list_filter = ["is_active"]


# The class to show which topic is unlocked
@admin.register(TopicAvailability)
class TopicAvailabilityAdmin(admin.ModelAdmin):
    list_display = ["school_class", "micro_skill", "is_available"]
    list_filter = ["is_available"]
