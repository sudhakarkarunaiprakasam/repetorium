"""Shared time and XP estimates for generated question difficulty levels."""

QUESTION_LEVELS = {
    1: {"label": "Easy", "minutes": 2, "xp": 1},
    2: {"label": "Medium", "minutes": 3, "xp": 2},
    3: {"label": "Hard", "minutes": 5, "xp": 3},
}


def question_level(difficulty: int) -> dict:
    if (isinstance(difficulty, bool) or not isinstance(difficulty, int)
            or difficulty not in QUESTION_LEVELS):
        raise ValueError("Question difficulty must be 1 (easy), 2 (medium), or 3 (hard).")
    return QUESTION_LEVELS[difficulty]
