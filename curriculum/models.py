"""
This file defines the database tables for curriculum.
"""

import random
import re

from django.db import models
from django.utils.text import slugify

from . import answer_math

# The regex used to strip the HTML tags from questions
_TAG_RE = re.compile(r"<[^>]+>")


# The class that represents the form levels for skills
class FormLevel(models.IntegerChoices):
    FORM_1 = 1, "Form 1"
    FORM_2 = 2, "Form 2"
    FORM_3 = 3, "Form 3"


# The class that handles the macro domain table
class MacroDomain(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="unlocks"
    )

    # The properties of the table
    class Meta:
        ordering = ["order", "name"]

    # The toString() function that prints the name of the macro domain
    def __str__(self):
        return self.name

    # A function to auto-generate slug from the name of macro domain
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# The class that handles the micro skill table
class MicroSkill(models.Model):
    macro_domain = models.ForeignKey(
        MacroDomain, on_delete=models.CASCADE, related_name="micro_skills"
    )
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    form_level = models.IntegerField(choices=FormLevel.choices, default=FormLevel.FORM_1)
    short_description = models.CharField(
        max_length=255,
        help_text="One plain-language sentence shown on cards.",
        blank=True,
    )
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="unlocks"
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Position within the learning path."
    )
    is_active = models.BooleanField(default=True)

    bkt_p_init = models.FloatField(
        default=0.4377, help_text="P(skill already known before any practice)."
    )
    bkt_p_transit = models.FloatField(
        default=0.1150, help_text="P(learning the skill on one opportunity)."
    )
    bkt_p_slip = models.FloatField(
        default=0.2273, help_text="P(answering wrong despite knowing the skill)."
    )
    bkt_p_guess = models.FloatField(
        default=0.3588, help_text="P(answering right without knowing the skill)."
    )
    bkt_fitted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When these parameters were last re-estimated from this "
                  "deployment's own attempts. Empty means they are the pooled "
                  "training fit, which is the normal case.",
    )
    bkt_fit_attempts = models.PositiveIntegerField(
        default=0,
        help_text="How many attempts the current parameters were estimated from.",
    )

    # Properties of the table
    class Meta:
        ordering = ["form_level", "order", "title"]

    # The toString() function that prints the form level and title of the micro skill
    def __str__(self):
        return f"{self.get_form_level_display()} · {self.title}"

    # A function to auto-generate the slug from the title on save
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


# The class that allows review notes to be written for each micro skill
class SkillNote(models.Model):
    micro_skill = models.OneToOneField(
        MicroSkill, on_delete=models.CASCADE, related_name="note"
    )
    learning_objective = models.CharField(max_length=255)
    explanation = models.TextField(
        help_text="Short conceptual explanation in plain English."
    )
    key_idea = models.TextField(
        blank=True, help_text="Shown in the soft-indigo 'Key idea' callout box."
    )

    # The toString() function to print the title of the review notes
    def __str__(self):
        return f"Notes: {self.micro_skill.title}"


# The class that allows worked examples to be stored for each micro skill
class WorkedExample(models.Model):
    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.CASCADE, related_name="worked_examples"
    )
    order = models.PositiveIntegerField(default=1)
    problem = models.TextField()
    solution_steps = models.TextField(help_text="Step-by-step solution (one step per line).")
    final_answer = models.CharField(max_length=255)

    # The properties of the table
    class Meta:
        ordering = ["order"]

    # The toString() function to print the order and skill title of the worked example
    def __str__(self):
        return f"Example {self.order} · {self.micro_skill.title}"

    # A function to split the stored solution text into lines to show line break
    @property
    def step_list(self):
        return [s for s in self.solution_steps.splitlines() if s.strip()]


# The class that handles the question table
class Question(models.Model):
    class QType(models.TextChoices):
        MCQ = "mcq", "Multiple choice"
        TRUE_FALSE = "true_false", "True / false"
        NUMERIC = "numeric", "Numeric / fraction"
        EXPRESSION = "expression", "Algebraic expression"
        FILL_BLANK = "fill_blank", "Fill in the blank"

    CHOICE_TYPES = (QType.MCQ, QType.TRUE_FALSE)

    micro_skill = models.ForeignKey(
        MicroSkill, on_delete=models.CASCADE, related_name="questions"
    )
    qtype = models.CharField(max_length=12, choices=QType.choices, default=QType.MCQ)
    stem = models.TextField(help_text="The question text (may contain maths).")
    correct_answer = models.CharField(max_length=255, blank=True)
    worked_solution = models.TextField(blank=True)

    baseline_difficulty = models.FloatField(
        default=0.5,
        help_text=(
            "Prior expected accuracy (0 = very hard, 1 = very easy). Leave at "
            "the default unless this question is known to be unusual."
        ),
    )

    times_attempted = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # The properties of the table
    class Meta:
        ordering = ["id"]

    # The toString() function to print the question's id and skill title
    def __str__(self):
        return f"Q{self.pk} · {self.micro_skill.title}"

    # A function to check whether the question is answered by picking a stored choice
    @property
    def uses_choices(self):
        return self.qtype in self.CHOICE_TYPES

    # A function to flag whether the question is selection-based
    @property
    def is_selection_based(self):
        return 1 if self.uses_choices else 0

    # A function to flag whether the question is input-based
    @property
    def is_input_based(self):
        return 0 if self.uses_choices else 1

    # A function to compute the question's historical accuracy
    @property
    def global_accuracy(self):
        if self.times_attempted == 0:
            return None
        return self.times_correct / self.times_attempted

    # A function to build a preview of the question
    @property
    def preview(self):
        text = _TAG_RE.sub(" ", self.stem)
        text = " ".join(text.split())
        return (text[:80] + "…") if len(text) > 80 else text

    # A function to check whether a submitted answer matches the stored correct answer
    def check_answer(self, submitted):

        # Clean the submitted answer
        submitted = (submitted or "").strip()

        # Validate the choice for selection-based questions
        if self.uses_choices:
            try:
                choice = self.choices.get(pk=int(submitted))
            except (ValueError, Choice.DoesNotExist):
                return False
            return choice.is_correct

        # Validate the answer for input-based questions and return true if they match exactly
        if _normalise(submitted) == _normalise(self.correct_answer):
            return True

        # If the input-based answer does not match
        return answer_math.check(submitted, self.correct_answer)

    # A function to display the correct answer
    def correct_answer_display(self):

        # Selection-based questions
        if self.uses_choices:
            correct = self.choices.filter(is_correct=True).first()
            return correct.text if correct else ""

        # Input-based questions
        return self.correct_answer

    # A function to split the worked solutions so that each step is displayed on a new line
    @property
    def solution_step_list(self):
        return [s for s in self.worked_solution.splitlines() if s.strip()]

    # A function to shuffle the choices for a selection-based question
    def choices_in_display_order(self, seed):
        options = list(self.choices.all())
        if self.qtype == self.QType.TRUE_FALSE or len(options) < 3:
            return options
        random.Random(f"{seed}:{self.pk}").shuffle(options)
        return options


# The class that allows multiple choices to be stored for each question
class Choice(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # Properties of the class
    class Meta:
        ordering = ["order", "id"]

    # A toString() function to return the text of the choice
    def __str__(self):
        return self.text


# A function to perform a quick normalization on an input-based answer to perform quick comparison
def _normalise(value):
    return "".join((value or "").lower().split())
