"""Typography rules shared by the line wrapper and the caption splitter.

Lives in its own module because renderer.py and segment_parser.py import each
other; putting the word list in either one creates a cycle that silently
degrades to "no rule applied".
"""

# Prepositions, conjunctions and particles that must not be left stranded at
# the end of a line - they belong to the word that follows.
HANGING_WORDS = {
    # ru prepositions
    "в", "во", "на", "за", "к", "ко", "с", "со", "о", "об", "обо", "от", "ото",
    "до", "по", "у", "из", "изо", "над", "надо", "под", "подо", "при", "про",
    "для", "без", "через", "между", "перед", "около", "после", "среди", "сквозь",
    # ru conjunctions / particles
    "и", "а", "но", "да", "или", "либо", "то", "что", "чтоб", "чтобы", "как",
    "где", "когда", "если", "хотя", "ведь", "же", "ли", "бы", "не", "ни",
    "уж", "вот", "лишь", "даже", "тоже", "также", "пусть",
    # en
    "a", "an", "the", "of", "in", "on", "at", "to", "by", "for", "and", "or",
    "but", "as", "is", "it", "if", "so", "we", "i",
}

_STRIP = ".,!?;:—-–«»\"'()"


def is_hanging(word):
    """True for a short function word that should travel with the next word."""
    bare = (word or "").strip().strip(_STRIP).lower()
    return bool(bare) and bare in HANGING_WORDS
