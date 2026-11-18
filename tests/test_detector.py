import cv2
import numpy as np
import pytest

from chest_counter.capture import region_to_pixels
from chest_counter.detector import (
    ChestStateMachine,
    TemplateMatcher,
    extract_template,
    load_templates,
    preprocess,
    save_template,
)

THRESHOLD = 200


def make_scene(with_prompt: bool, seed: int = 0, offset=(60, 40), text="TRUHE  [E] Durchsuchen"):
    """Synthetischer Spielausschnitt: verrauschter, dunkler bis mittelheller Hintergrund
    + optional weißer Hinweis-Text auf dunkler Box (wie das Fortnite-Interaktions-UI)."""
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 170, size=(240, 480, 3), dtype=np.uint8)
    if with_prompt:
        x, y = offset
        cv2.rectangle(frame, (x - 8, y - 30), (x + 330, y + 12), (20, 20, 20), -1)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return frame


def test_preprocess_keeps_only_bright_pixels():
    binary = preprocess(make_scene(False), THRESHOLD)
    assert cv2.countNonZero(binary) == 0
    binary = preprocess(make_scene(True), THRESHOLD)
    assert cv2.countNonZero(binary) > 100


def test_extract_template_crops_to_text():
    template = extract_template(preprocess(make_scene(True), THRESHOLD))
    assert template is not None
    assert template.shape[0] < 60 and template.shape[1] < 360
    assert extract_template(preprocess(make_scene(False), THRESHOLD)) is None


def test_matcher_finds_prompt_on_other_background_and_position():
    template = extract_template(preprocess(make_scene(True, seed=1), THRESHOLD))
    matcher = TemplateMatcher([template])
    hit = matcher.best_score(preprocess(make_scene(True, seed=7, offset=(110, 150)), THRESHOLD))
    miss = matcher.best_score(preprocess(make_scene(False, seed=7), THRESHOLD))
    other = matcher.best_score(
        preprocess(make_scene(True, seed=7, text="MUNITIONSKISTE  [E]"), THRESHOLD)
    )
    assert hit > 0.9
    assert miss < 0.3
    assert other < 0.75


def test_matcher_without_templates_scores_zero():
    assert TemplateMatcher().best_score(preprocess(make_scene(True), THRESHOLD)) == 0.0


def test_template_roundtrip(tmp_path):
    template = extract_template(preprocess(make_scene(True), THRESHOLD))
    first = save_template(tmp_path, template)
    second = save_template(tmp_path, template)
    assert first.name == "chest_1.png" and second.name == "chest_2.png"
    loaded = load_templates(tmp_path)
    assert len(loaded) == 2
    assert np.array_equal(loaded[0], template)


def run_sequence(machine, frames, fps=15):
    """frames: Liste von (prompt_visible, key_down). Gibt Anzahl gezählter Truhen zurück."""
    count = 0
    for i, (visible, key) in enumerate(frames):
        if machine.update(i / fps, visible, key):
            count += 1
    return count


def test_open_chest_counts_once():
    frames = [(False, False)] * 5 + [(True, False)] * 10 + [(True, True)] * 6 + [(False, True)] * 3 + [(False, False)] * 20
    assert run_sequence(ChestStateMachine(), frames) == 1


def test_tap_and_release_counts():
    frames = [(True, False)] * 10 + [(True, True)] * 2 + [(True, False)] * 3 + [(False, False)] * 10
    assert run_sequence(ChestStateMachine(), frames) == 1


def test_walking_away_does_not_count():
    frames = [(True, False)] * 20 + [(False, False)] * 20
    assert run_sequence(ChestStateMachine(), frames) == 0


def test_pressing_without_prompt_does_not_count():
    frames = [(False, True)] * 30
    assert run_sequence(ChestStateMachine(), frames) == 0


def test_cancelled_search_then_walk_away_does_not_count():
    # Taste kurz gedrückt, losgelassen, Hinweis bleibt > open_timeout, dann weggelaufen
    frames = [(True, False)] * 5 + [(True, True)] * 2 + [(True, False)] * 40 + [(False, False)] * 10
    assert run_sequence(ChestStateMachine(), frames) == 0


def test_single_frame_flicker_is_ignored():
    frames = [(True, False)] * 10 + [(True, True)] * 3 + [(False, True)] + [(True, True)] * 3 + [(False, True)] * 3
    assert run_sequence(ChestStateMachine(), frames) == 1


def test_two_chests_in_a_row():
    one = [(True, False)] * 5 + [(True, True)] * 5 + [(False, False)] * 30
    assert run_sequence(ChestStateMachine(), one + one) == 2


def test_cooldown_prevents_double_count():
    frames = [(True, False)] * 5 + [(True, True)] * 5 + [(False, True)] * 3 + [(True, True)] * 3 + [(False, True)] * 3
    assert run_sequence(ChestStateMachine(cooldown=1.5), frames) == 1


def test_region_to_pixels():
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    box = region_to_pixels([0.5, 0.5, 0.75, 1.0], monitor)
    assert box == {"left": 960, "top": 540, "width": 480, "height": 540}
    with pytest.raises(ValueError):
        region_to_pixels([0.5, 0.5, 0.4, 0.6], monitor)
