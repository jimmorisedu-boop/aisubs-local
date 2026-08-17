# Adapted from captacity (MIT License) - https://github.com/unconv/captacity
# Groups word-level transcript segments into on-screen caption chunks.

from typing import Callable

from typography import is_hanging

def has_partial_sentence(text):
    words = text.split()
    if len(words) >= 2:
        prev_word = words[-2].strip()
        if prev_word and prev_word[-1] == ".":
            return True
    return False

def parse(
    segments: list,
    fit_function: Callable,
    allow_partial_sentences: bool = False,
):
    captions = []
    caption = {
        "start": None,
        "end": 0,
        "words": [],
        "text": "",
    }

    # Merge words that are not separated by spaces
    for s, segment in enumerate(segments):
        for w, word in enumerate(segment["words"]):
            if w > 0 and word["word"][0] != " ":
                segments[s]["words"][w-1]["word"] += word["word"]
                segments[s]["words"][w-1]["end"] = word["end"]
                del segments[s]["words"][w]

    for segment in segments:
        for word in segment["words"]:
            if caption["start"] is None:
                caption["start"] = word["start"]

            text = caption["text"] + word["word"]

            caption_fits = allow_partial_sentences or not has_partial_sentence(text)
            caption_fits = caption_fits and fit_function(text)

            # A caption holding nothing but prepositions/conjunctions must never
            # be shown on its own, so it takes the next word even if that
            # overflows slightly - the renderer shrinks such a line to fit.
            if caption_fits or _only_hanging(caption):
                caption["words"].append(word)
                caption["end"] = word["end"]
                caption["text"] = text
            else:
                carried = _carry_hanging_words(caption, fit_function, word)
                captions.append(caption)
                caption = _new_caption(carried + [word])

    captions.append(caption)

    return captions

def _only_hanging(caption):
    words = caption.get("words") or []
    return bool(words) and all(is_hanging(w["word"]) for w in words)

def _new_caption(words):
    return {
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "words": list(words),
        "text": "".join(w["word"] for w in words),
    }

def _carry_hanging_words(caption, fit_function, next_word):
    """Moves trailing prepositions/conjunctions out of a finished caption so
    they appear together with the word they belong to, never stranded at the
    end. Stops as soon as the next caption would no longer fit."""
    carried = []
    while len(caption["words"]) > 1 and is_hanging(caption["words"][-1]["word"]):
        candidate = [caption["words"][-1]] + carried + [next_word]
        if not fit_function("".join(w["word"] for w in candidate)):
            break
        carried.insert(0, caption["words"].pop())

    if carried:
        caption["text"] = "".join(w["word"] for w in caption["words"])
        caption["end"] = caption["words"][-1]["end"]
    return carried
