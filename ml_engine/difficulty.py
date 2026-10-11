"""
The file to handle question difficulty calculation
(to replace CatBoost in case if the CatBoost model is missing)

Note: BKT only sees the skill. This handles the question difficulty.
"""

from django.db.models import Sum
from curriculum.models import Question

# Constants
PSEUDO_COUNT = 20       # This is to support shrinkage calculation
FALLBACK_PRIOR = Question._meta.get_field("baseline_difficulty").default


# A function to calculate the accuracy of the entire question bank
def prior_accuracy():

    # Sum up times_correct and times_attempted across all questions
    totals = Question.objects.aggregate(
        correct=Sum("times_correct"), attempted=Sum("times_attempted")
    )

    # If this is a brand-new deployment with no one answering question, then return the baseline difficulty
    attempted = totals["attempted"] or 0
    if not attempted:
        return FALLBACK_PRIOR

    # Conversely, calculate the global average for the question bank
    return (totals["correct"] or 0) / attempted


# A function to determine if a question should use own difficulty or the question bank's difficulty
def prior_for(question, bank_prior):

    # If the question's baseline difficulty is different from global baseline difficulty, return the question's one
    if question.baseline_difficulty != FALLBACK_PRIOR:
        return question.baseline_difficulty

    # If not, then return the question bank's average
    return bank_prior


# A function to estimate the question difficulty
def estimated_difficulty(question, bank_prior=None):

    # Retrieve the question bank's average accuracy
    if bank_prior is None:
        bank_prior = prior_accuracy()

    # Retrieve the question difficulty
    prior = prior_for(question, bank_prior)

    # Perform Bayesian shrinkage to estimate question probability
    #
    #               Correct count + Fixed sample * Default Probability
    #  Formula = ----------------------------------------------------------
    #                         Attempt count + Fixed sample
    #
    attempted = question.times_attempted or 0
    correct = question.times_correct or 0
    return (correct + PSEUDO_COUNT * prior) / (attempted + PSEUDO_COUNT)
