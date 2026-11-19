"""Montgomery County criminal justice data agent, on SYNTHETIC (made-up) data.

Stage 1: one question in, one checked answer out. Fixed rules (DETERMINISTIC_RULES_V0)
read the question; pandas counts the rows. No AI model.
Stage 2: the agent in Slack. The NVIDIA model reads the question and chooses one tool;
Python checks the choice, counts the rows through execute_call and writes every reply.
"""
from .core import AnalysisResult, answer_question, execute_call

__all__ = ["AnalysisResult", "answer_question", "execute_call"]
