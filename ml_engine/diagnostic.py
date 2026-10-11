"""
The file handles the recommendation logic for diagnostic quiz
(the 10-question quiz that students answer when they first log in to the system)
"""

from django.conf import settings
from curriculum.models import MicroSkill
from . import bkt, recommender, services


# A function that determines the skills that can be asked
def eligible_skills(student):

    from learning.models import SkillMastery

    # Retrieve the hidden skills and student mastery level
    hidden = services.hidden_skill_ids(student)
    masteries = {
        m.micro_skill_id: m for m in SkillMastery.objects.filter(student=student)
    }

    # Also retrieve the available skills in the system with their prerequisites
    skills = (
        MicroSkill.objects.filter(is_active=True)
        .select_related("macro_domain")
        .prefetch_related("prerequisites", "questions")
        .order_by("form_level", "order")
    )

    # Check through each skill
    available = []
    for skill in skills:

        # Skills that are hidden are not recommended
        if skill.id in hidden:
            continue

        # Retrieve the mastery level for the skill, then reject those skills that are mastered
        mastery = masteries.get(skill.id)
        p_known = mastery.bkt_mastery if mastery else bkt.params_for(skill).p_init
        if p_known >= settings.MASTERY_THRESHOLD:
            continue

        # Reject macro domains that are not unlocked
        if not services.is_macro_domain_unlocked(student, skill.macro_domain):
            continue

        # Reject micro skills that are not unlocked
        if not services.is_micro_skill_unlocked(student, skill, mastery):
            continue

        # Also skip the skills that do not have any remaining questions to ask
        if not any(q.is_active for q in skill.questions.all()):
            continue

        # If the skill passes all the checks, add it to the available skills list
        available.append(skill)

    # Lastly, return the list of available skills
    return available


# A function to retrieve the questions to be asked in a diagnostic test
def eligible_questions(student):

    # Loop through each skill and question
    questions = []
    for skill in eligible_skills(student):
        for question in skill.questions.all():

            # Skip questions that are not active (disabled by admin)
            if not question.is_active:
                continue

            # Since skills are already fetched, we pre-initialize it for performance purpose
            question.micro_skill = skill

            # Add the question to the list
            questions.append(question)

    # Return the list of available questions lastly
    return questions


# A function to determine the number of questions to be asked in a diagnostic test
def planned_length(student):

    # There are times where the number of question is insufficient, so this acts as a safety guard
    return min(settings.DIAGNOSTIC_SET_SIZE, len(eligible_questions(student)))


# A function to determine the next question to be asked in a diagnostic test
def next_question(session):

    # If the session is complete, return nothing
    if session.answered_count >= session.total_questions:
        return None

    # Retrieve the set of questions that has already been attempted, and return none if there's no more questions to ask
    seen_ids = set(session.attempts.values_list("question_id", flat=True))
    candidates = [
        q for q in eligible_questions(session.student) if q.id not in seen_ids
    ]
    if not candidates:
        return None

    # If there are still questions, use model to recommend questions
    ranked = recommender.rank_questions(session.student, candidates)
    return ranked[0].question if ranked else None


# A function to retrieve the mastery level of the topics from the diagnostic test
def micro_skill_report(student, session, *, recommended_skill=None):

    from learning.models import SkillMastery

    # Retrieve the list of attempted questions and the mastery level of the topics answered
    attempts = list(
        session.attempts.select_related("micro_skill").order_by("created_at", "id")
    )
    mastery_by_skill = {
        mastery.micro_skill_id: mastery
        for mastery in SkillMastery.objects.filter(student=student)
    }

    # Loop through each attempt to determine the skills attempted
    report = []
    seen_skill_ids = set()
    sampled_skills = []
    for attempt in attempts:
        skill = attempt.micro_skill
        if skill.id in seen_skill_ids:
            continue
        seen_skill_ids.add(skill.id)
        sampled_skills.append(skill)

    # Also include the skills that can be recommended but not recommended to students during the session
    if recommended_skill and recommended_skill.id not in seen_skill_ids:
        sampled_skills.append(recommended_skill)

    # For each skill
    for skill in sampled_skills:

        # Retrieve the mastery level of each skill
        mastery = mastery_by_skill.get(skill.id)

        # If the skill is attempted, add to the dictionary with the mastery level
        if mastery is not None and mastery.attempts > 0:
            value = mastery.bkt_mastery
            level = services.mastery_level_slug(value)
            report.append(
                {
                    "skill": skill,
                    "measured": True,
                    "percent": bkt.to_percent(value),
                    "level_slug": level,
                    "level_label": services.LEVEL_LABELS[level],
                }
            )

        # If the skill is not attempted, add to the dictionary without mastery level
        else:
            report.append(
                {
                    "skill": skill,
                    "measured": False,
                    "percent": 0,
                    "level_slug": "",
                    "level_label": "",
                }
            )

    # Return the skills with their mastery level
    return report


# A function to recommend the starting skill for student
def recommend_starting_skill(student):

    from learning.models import SkillMastery

    # Retrieve the skills with mastery level
    mastery_by_skill = {
        mastery.micro_skill_id: mastery
        for mastery in SkillMastery.objects.filter(student=student)
    }

    # Only include skills that are below the mastery threshold
    candidates = []
    for skill in eligible_skills(student):
        mastery = mastery_by_skill.get(skill.id)
        value = mastery.bkt_mastery if mastery else bkt.params_for(skill).p_init
        if value < settings.MASTERY_THRESHOLD:
            candidates.append((skill, value))

    # Return none if there's no skill for recommendation
    if not candidates:
        return None

    # If there is skill, sort then based on mastery in descending
    candidates.sort(
        key=lambda item: (
            -item[1], item[0].form_level, item[0].order, item[0].title
        )
    )

    # Return the first skill (the skill with the highest mastery level below 80%)
    return candidates[0][0]
