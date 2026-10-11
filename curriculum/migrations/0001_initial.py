"""
This file is the migration file used by the project to establish the database tables in the application.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MacroDomain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "prerequisites",
                    models.ManyToManyField(
                        blank=True, related_name="unlocks", to="curriculum.macrodomain"
                    ),
                ),
            ],
            options={
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="MicroSkill",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                ("slug", models.SlugField(blank=True, max_length=170, unique=True)),
                (
                    "form_level",
                    models.IntegerField(
                        choices=[(1, "Form 1"), (2, "Form 2"), (3, "Form 3")], default=1
                    ),
                ),
                (
                    "short_description",
                    models.CharField(
                        blank=True,
                        help_text="One plain-language sentence shown on cards.",
                        max_length=255,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0, help_text="Position within the learning path."
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "bkt_p_init",
                    models.FloatField(
                        default=0.4377,
                        help_text="P(skill already known before any practice).",
                    ),
                ),
                (
                    "bkt_p_transit",
                    models.FloatField(
                        default=0.115,
                        help_text="P(learning the skill on one opportunity).",
                    ),
                ),
                (
                    "bkt_p_slip",
                    models.FloatField(
                        default=0.2273,
                        help_text="P(answering wrong despite knowing the skill).",
                    ),
                ),
                (
                    "bkt_p_guess",
                    models.FloatField(
                        default=0.3588,
                        help_text="P(answering right without knowing the skill).",
                    ),
                ),
                (
                    "bkt_fitted_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When these parameters were last re-estimated from this deployment's own attempts. Empty means they are the pooled training fit, which is the normal case.",
                        null=True,
                    ),
                ),
                (
                    "bkt_fit_attempts",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="How many attempts the current parameters were estimated from.",
                    ),
                ),
                (
                    "macro_domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="micro_skills",
                        to="curriculum.macrodomain",
                    ),
                ),
                (
                    "prerequisites",
                    models.ManyToManyField(
                        blank=True, related_name="unlocks", to="curriculum.microskill"
                    ),
                ),
            ],
            options={
                "ordering": ["form_level", "order", "title"],
            },
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "qtype",
                    models.CharField(
                        choices=[
                            ("mcq", "Multiple choice"),
                            ("true_false", "True / false"),
                            ("numeric", "Numeric / fraction"),
                            ("expression", "Algebraic expression"),
                            ("fill_blank", "Fill in the blank"),
                        ],
                        default="mcq",
                        max_length=12,
                    ),
                ),
                (
                    "stem",
                    models.TextField(
                        help_text="The question text (may contain maths)."
                    ),
                ),
                ("correct_answer", models.CharField(blank=True, max_length=255)),
                ("worked_solution", models.TextField(blank=True)),
                (
                    "baseline_difficulty",
                    models.FloatField(
                        default=0.5,
                        help_text="Prior expected accuracy (0 = very hard, 1 = very easy). Leave at the default unless this question is known to be unusual.",
                    ),
                ),
                ("times_attempted", models.PositiveIntegerField(default=0)),
                ("times_correct", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "micro_skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="curriculum.microskill",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="Choice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=255)),
                ("is_correct", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="curriculum.question",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="SkillNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("learning_objective", models.CharField(max_length=255)),
                (
                    "explanation",
                    models.TextField(
                        help_text="Short conceptual explanation in plain English."
                    ),
                ),
                (
                    "key_idea",
                    models.TextField(
                        blank=True,
                        help_text="Shown in the soft-indigo 'Key idea' callout box.",
                    ),
                ),
                (
                    "micro_skill",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="note",
                        to="curriculum.microskill",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WorkedExample",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1)),
                ("problem", models.TextField()),
                (
                    "solution_steps",
                    models.TextField(
                        help_text="Step-by-step solution (one step per line)."
                    ),
                ),
                ("final_answer", models.CharField(max_length=255)),
                (
                    "micro_skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="worked_examples",
                        to="curriculum.microskill",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
            },
        ),
    ]
