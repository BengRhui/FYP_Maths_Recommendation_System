"""
This file handles the question recommendation of the system using CatBoost.
"""

from typing import NamedTuple
from django.conf import settings
from curriculum.models import MicroSkill
from . import bkt, difficulty, pear, services
from .features import FeatureContext
from .model_loader import get_model
from .services import hidden_skill_ids, is_micro_skill_unlocked

# A class to store the recommendation details
class Recommendation(NamedTuple):
    question: object
    p_correct: float
    similarity: float
    recommendation_score: float


# A function to calculate the probability of a student answering a question correctly when CatBoost is unavailable
def _heuristic_prob(question, mastery):

    # Retrieve the BKT params and the mastery level
    params = bkt.params_for(question.micro_skill)
    p_known = mastery.bkt_mastery if mastery else params.p_init

    # Use BKT to calculate the probability for the skill
    bkt_prob = bkt.predict_correct(p_known, params)

    # Calculate the probability from the question-level
    q_prob = difficulty.estimated_difficulty(question)

    # Get the average of both for the heuristic probability
    return 0.5 * bkt_prob + 0.5 * q_prob


# A function to calculate the probability of correctly answering a question, in a batch
def predict_correct_probs(questions, context):

    # Return empty if there are no questions
    if not questions:
        return []

    # Use the CatBoost model to calculate probabilities if available
    model = get_model()
    if model.is_ready:
        rows = [context.build(q) for q in questions]
        probs = model.predict_proba_batch(rows)
        if probs is not None:
            return probs

    # If CatBoost is not available, use the heuristics approach
    return [
        _heuristic_prob(q, context.mastery_for(q.micro_skill_id)) for q in questions
    ]


# A function to calculate the probability for the specific student and question
def predict_correct_prob(student, question, *, profile=None, mastery=None):
    context = FeatureContext(student, profile=profile)
    if mastery is not None:
        context.masteries[question.micro_skill_id] = mastery
    return predict_correct_probs([question], context)[0]


# A method to rank questions using scores from PEAR
def rank_questions(student, questions, *, context=None, knowledge=None):

    # Get the list of questions
    questions = list(questions)
    if not questions:
        return []

    # Retrieve student information and their mastery level for each skill
    context = context or FeatureContext(student)
    knowledge = knowledge or pear.build_knowledge_vector(student)

    # Pass both vectors into the CatBoost model for prediction
    probs = predict_correct_probs(questions, context)

    # Calculate the PEAR score for each question
    ranked = []
    for question, p_correct in zip(questions, probs):
        similarity = knowledge.similarity(question)
        ranked.append(
            Recommendation(
                question=question,
                p_correct=p_correct,
                similarity=similarity,
                recommendation_score=pear.proximity_score(p_correct, similarity),
            )
        )

    # Sort the scores in descending order
    ranked.sort(key=lambda r: r.recommendation_score, reverse=True)
    return ranked


# A method to select the next question for recommendation
def choose_next_question(session):

    # Retrieve the current student and skill
    student = session.student
    skill = session.micro_skill

    # Filter out the questions that are attempted in the current session
    answered_ids = set(session.attempts.values_list("question_id", flat=True))
    candidates = list(
        skill.questions.filter(is_active=True)
        .exclude(id__in=answered_ids)
        .select_related("micro_skill")
    )

    # Only reuse questions if there is not enough questions
    if not candidates:
        candidates = list(
            skill.questions.filter(is_active=True).select_related("micro_skill")
        )
    if not candidates:
        return None

    # Rank the questions and return the best one
    ranked = rank_questions(student, candidates)
    return ranked[0] if ranked else None


# A function to recommend the next suitable skill for students
def recommend_next_skills(student, n=3):
    from learning.models import SkillMastery

    # Retrieve the hidden skills and mastery levels for the student
    hidden = hidden_skill_ids(student)
    masteries = {
        m.micro_skill_id: m
        for m in SkillMastery.objects.filter(student=student).select_related(
            "micro_skill"
        )
    }

    # Loop through each skill to determine the valid skill for recommendation
    eligible = []
    for skill in _candidate_skills():

        # Hidden skills are rejected
        if skill.id in hidden:
            continue

        # Locked skills are rejected
        if not is_micro_skill_unlocked(student, skill):
            continue

        # Skills in locked macro domains are rejected
        if not services.is_macro_domain_unlocked(student, skill.macro_domain):
            continue

        # Skills that are already mastered are rejected
        mastery = masteries.get(skill.id)
        p_known = mastery.bkt_mastery if mastery else bkt.params_for(skill).p_init
        if p_known >= settings.MASTERY_THRESHOLD:
            continue

        # Add the skill to the list of eligible skills
        eligible.append((skill, mastery))

    # If there's no eligible skill, return an empty list
    if not eligible:
        return []

    # If there is, retrieve the questions for each skill
    questions = [
        q for skill, _ in eligible for q in skill.questions.all() if q.is_active
    ]

    # Rank all questions
    context = FeatureContext(student)
    knowledge = pear.build_knowledge_vector(student, masteries=masteries)
    ranked = rank_questions(
        student, questions, context=context, knowledge=knowledge
    )

    # Load the skill of the question, together with the score, into a dictionary
    best_by_skill = {}
    for item in ranked:
        best_by_skill.setdefault(item.question.micro_skill_id, item.recommendation_score)

    # Filter only skills in the eligible list, and sort it descending to get the best recommendation
    scored = [
        (skill, best_by_skill.get(skill.id, 0.0), mastery) for skill, mastery in eligible
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:n]


# A function to retrieve the skills that are available to students
def _candidate_skills():
    return list(
        MicroSkill.objects.filter(is_active=True)
        .select_related("macro_domain")
        .prefetch_related("prerequisites", "questions")
        .order_by("form_level", "order")
    )
