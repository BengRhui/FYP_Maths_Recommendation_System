"""
The file that collects data from the current system to be inputted to the champion model.
"""

from django.utils import timezone

# CatBoost is a tree-based model. Use -1 for imputation
MISSING = -1.0


# A function to calculate the difference in time
def _seconds_since(dt, now):
    if dt is None:
        return MISSING
    return max(0.0, (now - dt).total_seconds())


# A class that contains all the attributes for model prediction
class FeatureContext:

    # Constructor
    def __init__(self, student, *, profile=None, now=None):
        from learning.models import Attempt, SkillMastery, StudentProfile

        # Store the student object and the current timestamp
        self.student = student
        self.now = now or timezone.now()

        # Store the student profile or create a new one if it does not exist
        if profile is None:
            profile, _ = StudentProfile.objects.get_or_create(student=student)
        self.profile = profile

        # Load the students' mastery level on all skills
        self.masteries = {
            m.micro_skill_id: m
            for m in SkillMastery.objects.filter(student=student).select_related(
                "micro_skill"
            )
        }

        # Builds the student-question statistics by looping through each attempt and record it
        self._question_stats = {}
        attempts = (
            Attempt.objects.filter(student=student)
            .only("question_id", "is_correct", "created_at")
            .order_by("created_at")
        )
        for attempt in attempts:
            stats = self._question_stats.setdefault(
                attempt.question_id, {"count": 0, "last_outcome": None, "last_at": None}
            )
            stats["count"] += 1
            stats["last_outcome"] = 1.0 if attempt.is_correct else 0.0
            stats["last_at"] = attempt.created_at

        # Builds the student-skill statistics by looping through each skill and record attempts
        self._domain_stats = {}
        for mastery in self.masteries.values():
            if mastery.attempts == 0:
                continue
            skill = mastery.micro_skill
            bucket = self._domain_stats.setdefault(
                (skill.form_level, skill.macro_domain_id),
                {"correct": 0, "attempts": 0},
            )
            bucket["correct"] += mastery.correct
            bucket["attempts"] += mastery.attempts

    # A function to retrieve the mastery level for a skill
    def mastery_for(self, skill_id):
        return self.masteries.get(skill_id)

    # A function to prepare the feature set to be fed to the model for a given question
    def build(self, question, *, mastery=None):

        # Retrieve the skill, current timestamp, student profile, and mastery
        skill = question.micro_skill
        now = self.now
        profile = self.profile
        if mastery is None:
            mastery = self.masteries.get(question.micro_skill_id)

        # Retrieve the student-question statistics
        stats = self._question_stats.get(question.id)
        if stats is None:
            sq_count = 0
            sq_is_first_attempt = 1
            sq_last_attempt_outcome = MISSING
            sq_recency_sec = MISSING
        else:
            sq_count = stats["count"]
            sq_is_first_attempt = 0
            sq_last_attempt_outcome = stats["last_outcome"]
            sq_recency_sec = _seconds_since(stats["last_at"], now)

        # Retrieve the student statistics
        s_overall_accuracy = (
            profile.overall_accuracy if profile.overall_accuracy is not None else MISSING
        )
        s_time_since_last = _seconds_since(profile.last_attempt_at, now)

        # Retrieve the student-skill statistics (micro skills)
        has_micro_history = mastery is not None and mastery.attempts > 0
        if has_micro_history:
            ss_micro_mastery = (
                mastery.accuracy if mastery.accuracy is not None else MISSING
            )
            ss_micro_avg_attempts = float(mastery.attempts)
            ss_micro_recent_sec = _seconds_since(mastery.last_attempt_at, now)
            ss_micro_correct_streak = float(mastery.correct_streak)
            ss_micro_wrong_streak = float(mastery.wrong_streak)
            bkt_mastery = mastery.bkt_mastery
        else:
            ss_micro_mastery = MISSING
            ss_micro_avg_attempts = 0.0
            ss_micro_recent_sec = MISSING
            ss_micro_correct_streak = 0.0
            ss_micro_wrong_streak = 0.0
            bkt_mastery = MISSING

        # Retrieve the student-skill statistics (macro skills)
        domain = self._domain_stats.get((skill.form_level, skill.macro_domain_id))
        if domain and domain["attempts"]:
            ss_macro_mastery = domain["correct"] / domain["attempts"]
            ss_macro_avg_attempts = float(domain["attempts"])
        else:
            ss_macro_mastery = MISSING
            ss_macro_avg_attempts = 0.0

        # Retrieve question-level statistics
        q_global_accuracy = question.global_accuracy
        if q_global_accuracy is None:
            q_global_accuracy = MISSING

        return {
            "sq_prev_attempt_count": float(sq_count),
            "sq_is_first_attempt": sq_is_first_attempt,
            "sq_last_attempt_outcome": sq_last_attempt_outcome,
            "sq_recency_sec": sq_recency_sec,
            "s_overall_accuracy": s_overall_accuracy,
            "s_time_since_last": s_time_since_last,
            "s_total_attempts": float(profile.total_attempts),
            "s_correct_streak": float(profile.correct_streak),
            "ss_micro_mastery": ss_micro_mastery,
            "ss_micro_avg_attempts": ss_micro_avg_attempts,
            "ss_macro_mastery": ss_macro_mastery,
            "ss_macro_avg_attempts": ss_macro_avg_attempts,
            "ss_micro_recent_sec": ss_micro_recent_sec,
            "ss_micro_correct_streak": ss_micro_correct_streak,
            "ss_micro_wrong_streak": ss_micro_wrong_streak,
            "bkt_mastery": bkt_mastery,
            "q_global_attempt_count": float(question.times_attempted),
            "q_global_accuracy": q_global_accuracy,
            "is_selection_based": question.is_selection_based,
            "is_input_based": question.is_input_based,
            "is_cold_start": 1 if profile.is_cold_start else 0,
        }


# A function to build the feature set for the student and question
def build_features(student, question, *, profile=None, mastery=None, now=None):
    context = FeatureContext(student, profile=profile, now=now)
    return context.build(question, mastery=mastery)
