"""
This file adds the curriculum to the Django admin site.
"""

from django.contrib import admin

from .models import (
    Choice,
    MacroDomain,
    MicroSkill,
    Question,
    SkillNote,
    WorkedExample,
)


# The class to add worked examples into the review notes
class WorkedExampleInline(admin.StackedInline):
    model = WorkedExample
    extra = 0


# The class to add review notes to a skill
class SkillNoteInline(admin.StackedInline):
    model = SkillNote
    extra = 0


# The class to add macro domains to the admin site
@admin.register(MacroDomain)
class MacroDomainAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    prepopulated_fields = {"slug": ("name",)}


# The class to add micro skills to the admin site
@admin.register(MicroSkill)
class MicroSkillAdmin(admin.ModelAdmin):
    list_display = [
        "title", "macro_domain", "form_level", "order", "is_active", "bkt_summary",
    ]
    list_filter = ["form_level", "macro_domain", "is_active"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["prerequisites"]
    inlines = [SkillNoteInline, WorkedExampleInline]
    readonly_fields = ["bkt_fitted_at", "bkt_fit_attempts"]
    fieldsets = [
        (None, {
            "fields": [
                "macro_domain", "title", "slug", "form_level", "order",
                "short_description", "prerequisites", "is_active",
            ]
        }),
        ("Bayesian Knowledge Tracing", {
            "classes": ["collapse"],
            "description": (
                "The pooled pyBKT fit from the training corpus — the mean of "
                "its 18 non-degenerate per-skill fits — applied to every skill. "
                "Not re-estimated from this deployment's answers: with a few "
                "hundred attempts per skill an online fit tracked student "
                "ability markedly worse than these do. Edit only if a skill is "
                "known to behave differently."
            ),
            "fields": [
                "bkt_p_init", "bkt_p_transit", "bkt_p_slip", "bkt_p_guess",
                "bkt_fitted_at", "bkt_fit_attempts",
            ],
        }),
    ]

    # A function to display the default BKT parameters
    @admin.display(description="BKT (init/transit/slip/guess)")
    def bkt_summary(self, obj):
        source = f"{obj.bkt_fit_attempts} attempts" if obj.bkt_fitted_at else "initial"
        return (
            f"{obj.bkt_p_init:.2f} / {obj.bkt_p_transit:.2f} / "
            f"{obj.bkt_p_slip:.2f} / {obj.bkt_p_guess:.2f}  ({source})"
        )


# The class to edit the answer options of a question
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


# The class to add and manage questions on the admin site
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "micro_skill", "qtype", "baseline_difficulty", "times_attempted", "times_correct"]
    list_filter = ["qtype", "micro_skill__form_level", "micro_skill"]
    search_fields = ["stem"]
    inlines = [ChoiceInline]
