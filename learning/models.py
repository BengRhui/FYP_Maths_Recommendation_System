"""
This file defines the database tables related to student learning profiles.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from curriculum.models import MicroSkill, Question
from ml_engine import bkt, services


# The class that handles the table to store student profiles
class StudentProfile(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    total_attempts = models.PositiveIntegerField(default=0)
    total_correct = models.PositiveIntegerField(default=0)
    correct_streak = models.PositiveIntegerField(default=0)
    wrong_streak = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    diagnostic_completed_at = models.DateTimeField(null=True, blank=True)

    # The toString() method that prints the name of the student
    def __str__(self):
        return f"Profile: {self.student}"

    # A function to return the student's overall accuracy
    @property
    def overall_accuracy(self):
        if self.total_attempts == 0:
            return None
        return self.total_correct / self.total_attempts

    # A function to check whether the student has made any attempts yet
    @property
    def is_cold_start(self):
        return self.total_attempts == 0

    # A function to check whether the student still needs to sit the diagnostic
    @property
    def needs_diagnostic(self):
        return self.diagnostic_completed_at is None


# The class that handles the table to store student mastery level for each micro-skills
class SkillMastery(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="masteries"
    )
    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.CASCADE, related_name="masteries"
    )
    bkt_mastery = models.FloatField(default=0.20)
    attempts = models.PositiveIntegerField(default=0)
    correct = models.PositiveIntegerField(default=0)
    correct_streak = models.PositiveIntegerField(default=0)
    wrong_streak = models.PositiveIntegerField(default=0)
    notes_viewed = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    # Properties of the table
    class Meta:
        unique_together = ("student", "micro_skill")
        verbose_name_plural = "skill masteries"

    # The toString() method that prints the name of the student, the title of the micro-skill, and the mastery level
    def __str__(self):
        return f"{self.student} · {self.micro_skill.title} · {self.bkt_mastery:.2f}"

    # A function that prevents attempts from being stored into DB when prerequisites are not unlocked
    def clean(self):
        from django.conf import settings as dj_settings
        from django.core.exceptions import ValidationError

        # Do nothing if the mastery level is not high enough or if the micro-skill is not set
        if self.bkt_mastery < dj_settings.MASTERY_THRESHOLD or not self.micro_skill_id:
            return

        # Do nothing if there is no prerequisite left
        prereqs = list(self.micro_skill.prerequisites.all())
        if not prereqs:
            return

        # Check the prerequisite that the student has mastered
        mastered_ids = set(
            SkillMastery.objects.filter(
                student_id=self.student_id,
                micro_skill__in=prereqs,
                bkt_mastery__gte=dj_settings.MASTERY_THRESHOLD,
            )
            .exclude(pk=self.pk)
            .values_list("micro_skill_id", flat=True)
        )

        # Check if there are prerequisites not fulfilled
        unmet = [p.title for p in prereqs if p.id not in mastered_ids]

        # If yes, raise an exception
        if unmet:
            raise ValidationError(
                f"Cannot mark '{self.micro_skill.title}' mastered: its "
                f"prerequisite(s) {', '.join(unmet)} aren't mastered for this "
                "student yet."
            )

    # A function to return the student's accuracy on a specific skill
    @property
    def accuracy(self):
        if self.attempts == 0:
            return None
        return self.correct / self.attempts

    # A function to return the status for the skill's progress
    @property
    def status(self):
        from django.conf import settings as dj_settings

        if self.attempts == 0:
            return "available"
        if self.bkt_mastery >= dj_settings.MASTERY_THRESHOLD:
            return "mastered"
        return "in_progress"

    # A function to return the mastery tier for the skill
    @property
    def level_slug(self):
        return services.mastery_level_slug(self.bkt_mastery)

    # A function to return the student-facing label for the mastery tier
    @property
    def level_label(self):
        return services.LEVEL_LABELS[self.level_slug]

    # A function to return the mastery value converted to a percentage
    @property
    def mastery_percent(self):
        return bkt.to_percent(self.bkt_mastery)


# The class that handles the table to store student practice sessions
class PracticeSession(models.Model):
    class Kind(models.TextChoices):
        PRACTICE = "practice", "Adaptive practice"
        DIAGNOSTIC = "diagnostic", "Diagnostic"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions"
    )
    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sessions",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.PRACTICE)
    total_questions = models.PositiveIntegerField(default=5)
    current_question = models.ForeignKey(
        Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    current_predicted_prob = models.FloatField(null=True, blank=True)
    current_proximity = models.FloatField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)
    is_complete = models.BooleanField(default=False)
    mastery_before = models.FloatField(null=True, blank=True)
    mastery_after = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Properties of the table
    class Meta:
        ordering = ["-created_at"]

    # The toString() method that prints the name of the student, the title of the micro-skill, and the score
    def __str__(self):
        skill = self.micro_skill.title if self.micro_skill else "Diagnostic"
        return f"{self.student} · {skill} · {self.score}/{self.total_questions}"

    # A function to return how many questions in this session have been answered
    @property
    def answered_count(self):
        return self.attempts.count()

    # A function to return the number of the next question to be shown
    @property
    def next_question_number(self):
        return self.answered_count + 1

    # A function to return the change in mastery over this session
    @property
    def mastery_delta(self):
        if self.mastery_before is None or self.mastery_after is None:
            return None
        return self.mastery_after - self.mastery_before


# The class that handles the table to store student attempts after answering questions
class Attempt(models.Model):
    session = models.ForeignKey(
        PracticeSession, on_delete=models.CASCADE, related_name="attempts",
        null=True, blank=True,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="attempts"
    )
    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.CASCADE, related_name="attempts"
    )
    submitted_answer = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)
    predicted_prob = models.FloatField(null=True, blank=True)
    proximity_score = models.FloatField(null=True, blank=True)
    response_time_sec = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Properties of the table
    class Meta:
        ordering = ["-created_at"]

    # The toString() method that prints the name of the student, the question id, and whether the answer was correct or incorrect
    def __str__(self):
        outcome = "correct" if self.is_correct else "incorrect"
        return f"{self.student} · Q{self.question_id} · {outcome}"

    # A function to check whether this attempt came from the diagnostic test
    @property
    def is_diagnostic(self):
        return bool(
            self.session_id
            and self.session
            and self.session.kind == PracticeSession.Kind.DIAGNOSTIC
        )

    # A function to return the submitted answer in text
    @property
    def submitted_answer_display(self):

        # Blank answers
        if not self.submitted_answer:
            return ""

        # Input-based answers
        if not self.question.uses_choices:
            return self.submitted_answer

        # Selection-based answers
        try:
            pk = int(self.submitted_answer)
        except ValueError:
            return self.submitted_answer
        choice = self.question.choices.filter(pk=pk).first()
        return choice.text if choice else self.submitted_answer


# The class that handles the table to store student mastery snapshots
class MasterySnapshot(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mastery_snapshots"
    )
    overall_mastery = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    # Properties of the table
    class Meta:
        ordering = ["recorded_at"]

    # The toString() method that prints the name of the student, the overall mastery level, and the date of the snapshot
    def __str__(self):
        return f"{self.student} · {self.overall_mastery:.2f} @ {self.recorded_at:%Y-%m-%d}"
