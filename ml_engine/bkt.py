"""
The file to handle BKT-related features.
"""

import math
from dataclasses import dataclass


# A class to hold the parameters for BKT (obtained from the JSON file exported by script in research directory)
@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.4377
    p_transit: float = 0.1150
    p_slip: float = 0.2273
    p_guess: float = 0.3588


# Store the initial values of BKT params
INITIAL_PARAMS = BKTParams()

# These are the boundaries set to avoid these errors:
_MAX_GUESS = 0.5                # Students can guess answers without knowing the skill
_MAX_SLIP = 0.5                 # Students make mistakes half of the time
_MAX_TRANSIT = 0.3              # Wrong attempts can increase mastery
_MAX_GUESS_PLUS_SLIP = 0.75     # If guess + slip >= 1, model cannot learn
_PRIOR_RANGE = (0.05, 0.5)      # Skill is known before practice
_PARAM_FLOOR = 0.01             # Slip and guess cannot be 0
_PRIOR_WEIGHT = 20              # Overly small number of attempts might be unstable when BKT is applied on own system
MASTERY_FLOOR = 0.02            # Mastery cannot be exactly 0 in BKT, then it can't progress
MASTERY_CEILING = 0.995         # Mastery cannot be exactly 1 in BKT, then it can't regress


# A function to make sure that the mastery levels are between the boundaries
def _clamp(p_known: float) -> float:
    return min(MASTERY_CEILING, max(MASTERY_FLOOR, p_known))


# A function to convert mastery level to percentages
def to_percent(p_known: float) -> int:
    return min(100, math.ceil(p_known * 100))


# A function to return the BKT params for a skill
def params_for(skill) -> BKTParams:

    # If a skill does not have params, return the baseline params
    if skill is None:
        return INITIAL_PARAMS

    # If not, return the params for the skill
    return BKTParams(
        p_init=skill.bkt_p_init,
        p_transit=skill.bkt_p_transit,
        p_slip=skill.bkt_p_slip,
        p_guess=skill.bkt_p_guess,
    )


# A function that calculates the posterior of the BKT formula
def _posterior(p_known: float, correct: bool, prm: BKTParams) -> float:

    # First, extract the p_known and limit to boundaries
    p_known = _clamp(p_known)

    # If it's a correct attempt
    if correct:
        num = p_known * (1 - prm.p_slip)                # Students know and did not slip
        den = num + (1 - p_known) * prm.p_guess         # Students did not know and guessed the answer

    # If it's an incorrect attempt
    else:
        num = p_known * prm.p_slip                      # Students know the concept but slipped
        den = num + (1 - p_known) * (1 - prm.p_guess)   # Students do not know the concept and guessed wrongly

    # Safety check, cannot divide by zero
    if den == 0:
        return p_known

    # Probability of knowing the concept = cases where they actually know / all possibilities of student getting correct
    return num / den


# A function to update mastery of a skill (following BKT formula)
def update(p_known: float, correct: bool, prm: BKTParams = INITIAL_PARAMS) -> float:

    # First calculates the posterior
    posterior = _posterior(p_known, correct, prm)

    # Then apply the learning step, where mastery = student knows + student doesn't know initially but learnt in this attempt
    result = posterior + (1 - posterior) * prm.p_transit
    return _clamp(result)


# A function to predict correctness probability using BKT in case champion model is not working
def predict_correct(p_known: float, prm: BKTParams = INITIAL_PARAMS) -> float:
    return p_known * (1 - prm.p_slip) + (1 - p_known) * prm.p_guess


# A function to perform Bayesian shrinkage to avoid small data sample from leading to inaccurate predictions
def _shrink(empirical, n, initial):

    # If the sample size is not provided, then do nothing
    if not n:
        return initial

    # Else, perform Bayesian shrinkage. In simple words, the formula is:
    #
    #                (New calculated value * sample size) + (Previous value * Threshold count)
    #    New value = ---------------------------------------------------------------------------
    #                                     Sample size + Threshold count
    #
    # For example, if the value of the difficulty of a hard question is 0.2, but three smart students answer them correctly
    # Without shrinkage, this becomes 3/3 = 1, which is not correct.
    # So, shrinkage turns it into (0.2 * 20 + 3 * 1) / (20 + 3) = 7/23 = 0.3
    # This preserves the validity of data
    return (n * empirical + _PRIOR_WEIGHT * initial) / (n + _PRIOR_WEIGHT)


# Return the bounded value of a number
def _bounded(value, low, high):
    return min(high, max(low, value))


# A function to check all BKT params in one shot
def bound_params(prm: BKTParams) -> BKTParams:

    # Bound the p_slip and p_guess
    p_slip = _bounded(prm.p_slip, _PARAM_FLOOR, _MAX_SLIP)
    p_guess = _bounded(prm.p_guess, _PARAM_FLOOR, _MAX_GUESS)

    # Scale down the p_slip and p_guess if they are too large
    if p_slip + p_guess >= _MAX_GUESS_PLUS_SLIP:
        scale = _MAX_GUESS_PLUS_SLIP / (p_slip + p_guess)
        p_slip *= scale
        p_guess *= scale

    # Return the cleaned BKT params
    return BKTParams(
        p_init=_bounded(prm.p_init, *_PRIOR_RANGE),
        p_transit=_bounded(prm.p_transit, _PARAM_FLOOR, _MAX_TRANSIT),
        p_slip=p_slip,
        p_guess=p_guess,
    )

# Perform shrinkage on all BKT params at once
def shrink_towards(prm: BKTParams, n, initial: BKTParams = INITIAL_PARAMS) -> BKTParams:
    return BKTParams(**{
        f: _shrink(getattr(prm, f), n, getattr(initial, f))
        for f in ("p_init", "p_transit", "p_slip", "p_guess")
    })
