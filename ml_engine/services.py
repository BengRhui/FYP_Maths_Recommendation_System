"""
This file connects the frontend and backend of students with the recommendation logic.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import bkt

# The wording for levels to be shown to students
LEVEL_LABELS = {
    "secure": "Mastered",
    "developing": "Getting there",
    "beginning": "Needs practice",
}


# A function to return the associated word based on the threshold defined
def mastery_level_slug(p_known):
    if p_known >= settings.MASTERY_THRESHOLD:
        return "secure"
    if p_known >= settings.MASTERY_DEVELOPING:
        return "developing"
    return "beginning"


# A function to retrieve the profile via the student object
def get_profile(student):
    from learning.models import StudentProfile

    # Retrieve profile for the student from DB, or create one if it doesn't exist
    profile, _ = StudentProfile.objects.get_or_create(student=student)
    return profile


# A function that records the details when the diagnostic test is completed
def mark_diagnostic_complete(student, when=None):

    # First, retrieve the student profile
    profile = get_profile(student)

    # If the completion time is not marked, set it to current time and update to DB
    if profile.diagnostic_completed_at is None:
        profile.diagnostic_completed_at = when or timezone.now()
        profile.save(update_fields=["diagnostic_completed_at"])

    # Return the student profile
    return profile


# A function to retrieve the mastery level of students for a specific skill
def get_mastery(student, skill):
    from learning.models import SkillMastery

    # Retrieve the mastery level for the student and skill from DB
    mastery, _ = SkillMastery.objects.get_or_create(
        student=student,
        micro_skill=skill,
        defaults={"bkt_mastery": bkt.params_for(skill).p_init},
    )
    return mastery


# A function to determine if a skill is unlocked
def is_micro_skill_unlocked(student, skill, mastery=None):
    from learning.models import SkillMastery

    # Retrieve the list of prerequisites for the skill
    prereqs = list(skill.prerequisites.all())

    # Directly return True if there are no prerequisites
    if not prereqs:
        return True

    # Retrieve the existing mastery from the DB
    if mastery is None:
        mastery = SkillMastery.objects.filter(student=student, micro_skill=skill).first()

    # If mastery is above the threshold, then the skill is considered unlocked
    if mastery is not None and mastery.bkt_mastery >= settings.MASTERY_THRESHOLD:
        return True

    # If not, then retrieve the prerequisites mastered by the student
    mastered_ids = set(
        SkillMastery.objects.filter(
            student=student,
            micro_skill__in=prereqs,
            bkt_mastery__gte=settings.MASTERY_THRESHOLD,
        ).values_list("micro_skill_id", flat=True)
    )

    # Only return true if all prerequisites are mastered
    return all(p.id in mastered_ids for p in prereqs)


# A function that returns the list of prerequisite that has not fulfilled
def unmet_prerequisites(student, skill):
    from learning.models import SkillMastery

    # Retrieve the set of prerequisites for the skill
    prereqs = list(skill.prerequisites.all())

    # Retrieve the prerequisites mastered by the student
    mastered_ids = set(
        SkillMastery.objects.filter(
            student=student,
            micro_skill__in=prereqs,
            bkt_mastery__gte=settings.MASTERY_THRESHOLD,
        ).values_list("micro_skill_id", flat=True)
    )

    # Extract the list of unmastered skills and return
    return [p for p in prereqs if p.id not in mastered_ids]


# A function that returns the state of a skill (locked, in progress, mastered)
def skill_state(student, skill, mastery=None):

    # Attempt to retrieve mastery from DB
    if mastery is None:
        from learning.models import SkillMastery
        mastery = SkillMastery.objects.filter(student=student, micro_skill=skill).first()

    # Return locked if the skill is not unlocked
    if not is_micro_skill_unlocked(student, skill, mastery):
        return "locked"

    # If the skill is unlocked but does not have mastery or attempt, return available
    if mastery is None or mastery.attempts == 0:
        return "available"

    # Else, return the current mastery status
    return mastery.status


# A function that returns the skills hidden from students
def hidden_skill_ids(student):
    from classes.models import TopicAvailability
    return set(
        TopicAvailability.objects.filter(
            school_class__memberships__student=student,
            school_class__memberships__is_active=True,
            school_class__memberships__restrictions_disabled=False,
            is_available=False,
        ).values_list("micro_skill_id", flat=True)
    )


# A function that calculates the overall mastery of students
def overall_mastery(student):
    from learning.models import SkillMastery

    # Retrieve the list of BKT mastery for each skill
    values = list(
        SkillMastery.objects.filter(student=student, attempts__gt=0).values_list(
            "bkt_mastery", flat=True
        )
    )

    # Return 0 if there are no values
    if not values:
        return 0.0

    # If there are values, return the average
    return sum(values) / len(values)


# A function that calculates the overall learning time of students
def _practice_hours(student, since=None):
    from learning.models import Attempt

    # Retrieve the list of attempts for the student
    qs = Attempt.objects.filter(student=student)

    # If a specific time is provided, filter the attempts
    if since is not None:
        qs = qs.filter(created_at__gte=since)

    # Calculate the total learning time in seconds and convert to hours
    total_seconds = qs.aggregate(total=Sum("response_time_sec"))["total"] or 0
    return total_seconds / 3600


# A function that calculates the weekly learning time of students
def hours_this_week(student):

    # Calculate the start of the current week
    now = timezone.localtime(timezone.now())
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Filter the attempts to the current week and calculate the time
    return _practice_hours(student, since=week_start)


# A function that acts as the interface between services.py and views.py for total learning hours
def hours_all_time(student):
    return _practice_hours(student)


# A function that records the attempt history of students
def record_attempt(
    student,
    question,
    submitted_answer,
    *,
    session=None,
    predicted_prob=None,
    proximity_score=None,
    response_time_sec=None,
):
    # Everything must be performed together to prevent inconsistencies
    with transaction.atomic():
        from learning.models import Attempt

        # Retrieve statistics
        now = timezone.now()
        is_correct = question.check_answer(submitted_answer)
        skill = question.micro_skill

        # Create a new attempt object
        attempt = Attempt.objects.create(
            session=session,
            student=student,
            question=question,
            micro_skill=skill,
            submitted_answer=str(submitted_answer)[:255],
            is_correct=is_correct,
            predicted_prob=predicted_prob,
            proximity_score=proximity_score,
            response_time_sec=response_time_sec,
            created_at=now,
        )

        # Question-related statistics
        question.times_attempted += 1
        if is_correct:
            question.times_correct += 1
        question.save(update_fields=["times_attempted", "times_correct"])

        # Student-related statistics
        profile = get_profile(student)
        profile.total_attempts += 1
        if is_correct:
            profile.total_correct += 1
            profile.correct_streak += 1
            profile.wrong_streak = 0
        else:
            profile.wrong_streak += 1
            profile.correct_streak = 0
        profile.last_attempt_at = now
        profile.save()

        # Mastery-related statistics
        mastery = get_mastery(student, skill)
        params = bkt.params_for(skill)
        mastery.bkt_mastery = bkt.update(mastery.bkt_mastery, is_correct, params)
        mastery.attempts += 1
        if is_correct:
            mastery.correct += 1
            mastery.correct_streak += 1
            mastery.wrong_streak = 0
        else:
            mastery.wrong_streak += 1
            mastery.correct_streak = 0
        mastery.last_attempt_at = now
        mastery.save()

    # Return the attempt object and its correctness
    return attempt, is_correct


# A function that determines if a macro domain is unlocked (but system does not set prerequisite for macro domains)
def is_macro_domain_unlocked(student, macro_domain):
    from learning.models import SkillMastery

    # Obtain the list of prerequisites for the macro domain
    prereqs = list(macro_domain.prerequisites.all())
    if not prereqs:
        return True

    # Loop through each macro domain prerequisite
    for prereq in prereqs:

        # Retrieve the micro skills for the macro domain
        prereq_skills = prereq.micro_skills.filter(is_active=True)

        # Check if students have actually attempted the micro skills
        attempted_masteries = SkillMastery.objects.filter(
            student=student,
            micro_skill__in=prereq_skills,
            attempts__gt=0
        )

        # If totally none, then lock the macro domain
        if not attempted_masteries.exists():
            return False

        # Otherwise, calculate the average BKT mastery for the micro skills
        avg_mastery = sum(m.bkt_mastery for m in attempted_masteries) / attempted_masteries.count()

        # Lock if the mastery is below threshold
        if avg_mastery < settings.MASTERY_THRESHOLD:
            return False

    # Only return true when all prerequisites are satisfied
    return True
