"""Non-destructive output naming for batch jobs."""

from pathlib import Path


def plan_output_paths(videos, output_dir):
    output_dir = Path(output_dir)
    used = set()
    result = []
    for video in videos:
        stem = Path(video).stem + "_captioned"
        candidate = stem
        suffix = 2
        while candidate.lower() in used or (output_dir / f"{candidate}.mp4").exists():
            candidate = f"{stem}_{suffix}"
            suffix += 1
        used.add(candidate.lower())
        result.append(str(output_dir / f"{candidate}.mp4"))
    return result
