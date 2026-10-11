"""
This file is the migration file used by the project to establish the database tables in the application.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("curriculum", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MasterySnapshot",
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
                ("overall_mastery", models.FloatField()),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mastery_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["recorded_at"],
            },
        ),
        migrations.CreateModel(
            name="PracticeSession",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("practice", "Adaptive practice"),
                            ("diagnostic", "Diagnostic"),
                        ],
                        default="practice",
                        max_length=12,
                    ),
                ),
                ("total_questions", models.PositiveIntegerField(default=5)),
                ("current_predicted_prob", models.FloatField(blank=True, null=True)),
                ("current_proximity", models.FloatField(blank=True, null=True)),
                ("score", models.PositiveIntegerField(default=0)),
                ("is_complete", models.BooleanField(default=False)),
                ("mastery_before", models.FloatField(blank=True, null=True)),
                ("mastery_after", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "current_question",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="curriculum.question",
                    ),
                ),
                (
                    "micro_skill",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sessions",
                        to="curriculum.microskill",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Attempt",
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
                ("submitted_answer", models.CharField(blank=True, max_length=255)),
                ("is_correct", models.BooleanField(default=False)),
                ("predicted_prob", models.FloatField(blank=True, null=True)),
                ("proximity_score", models.FloatField(blank=True, null=True)),
                ("response_time_sec", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "micro_skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="curriculum.microskill",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="curriculum.question",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="learning.practicesession",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StudentProfile",
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
                ("total_attempts", models.PositiveIntegerField(default=0)),
                ("total_correct", models.PositiveIntegerField(default=0)),
                ("correct_streak", models.PositiveIntegerField(default=0)),
                ("wrong_streak", models.PositiveIntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                (
                    "diagnostic_completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SkillMastery",
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
                ("bkt_mastery", models.FloatField(default=0.2)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("correct", models.PositiveIntegerField(default=0)),
                ("correct_streak", models.PositiveIntegerField(default=0)),
                ("wrong_streak", models.PositiveIntegerField(default=0)),
                ("notes_viewed", models.BooleanField(default=False)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                (
                    "micro_skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="masteries",
                        to="curriculum.microskill",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="masteries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "skill masteries",
                "unique_together": {("student", "micro_skill")},
            },
        ),
    ]
