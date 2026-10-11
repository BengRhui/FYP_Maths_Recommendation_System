"""
This file handles the implementation of the revised PEAR formula that prioritizes questions with moderate difficulty.
"""

import math

from curriculum.models import MicroSkill

from . import bkt

# Class to represent student's current mastery level across all skills
class KnowledgeVector:

    # KnowledgeVector stores two things: mapping of skill and mastery level, and |vector| (named as norm)
    __slots__ = ("mastery_by_skill", "norm")

    # Constructor
    def __init__(self, mastery_by_skill, norm):
        self.mastery_by_skill = mastery_by_skill
        self.norm = norm

    # A method to calculate the similarity between student knowledge vector and question skill vector
    def similarity(self, question):
        return self.similarity_for_skill(question.micro_skill_id)   # Each question is only associated with one skill

    # A method to calculate the similarity for a specific skill, using mastery / norm
    def similarity_for_skill(self, skill_id):
        if self.norm <= 0:
            return 0.0
        return self.mastery_by_skill.get(skill_id, 0.0) / self.norm

    # A method to retrieve the mastery level of a specific skill
    def mastery(self, skill_id):
        return self.mastery_by_skill.get(skill_id, 0.0)

# The method to build student knowledge vector
def build_knowledge_vector(student, *, skills=None, masteries=None):

    from learning.models import SkillMastery

    # Create the skill list if no skill is created yet
    if skills is None:
        skills = list(MicroSkill.objects.filter(is_active=True).only("id", "slug"))

    # Create the mastery list if no mastery is created yet
    if masteries is None:
        masteries = {
            m.micro_skill_id: m
            for m in SkillMastery.objects.filter(student=student).only(
                "micro_skill_id", "bkt_mastery"
            )
        }

    # Load the mastery values for each skill
    mastery_by_skill = {}
    for skill in skills:
        record = masteries.get(skill.id)
        if record is not None:
            value = record.bkt_mastery
        else:
            value = bkt.params_for(skill).p_init   # Use BKT prior if no mastery
        mastery_by_skill[skill.id] = value

    # Calculate the vector magnitude (norm) and return the vector
    norm = math.sqrt(sum(v * v for v in mastery_by_skill.values()))
    return KnowledgeVector(mastery_by_skill, norm)

# A function to calculate score for each question
def proximity_score(p_correct, similarity):

    # Apply the revised PEAR formula: [1 - 2 * |0.5 - p_correct|] * cos_sim(student mastery, question skill)
    difficulty = 1.0 - 2.0 * abs(0.5 - p_correct)
    return difficulty * similarity
