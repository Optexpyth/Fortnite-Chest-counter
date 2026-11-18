import json

from chest_counter.config import DEFAULT_CONFIG, load_config
from chest_counter.storage import ChestStats


def test_new_file_starts_at_zero(tmp_path):
    stats = ChestStats(tmp_path / "stats.json")
    assert stats.total == 0
    assert not stats.exists


def test_add_persists(tmp_path):
    path = tmp_path / "stats.json"
    stats = ChestStats(path)
    stats.add(1)
    stats.add(1)
    assert ChestStats(path).total == 2
    assert json.loads(path.read_text())["total"] == 2


def test_decrement_never_below_zero(tmp_path):
    stats = ChestStats(tmp_path / "stats.json")
    stats.add(1)
    assert stats.add(-1) == 0
    assert stats.add(-1) == 0


def test_set_start_value(tmp_path):
    path = tmp_path / "stats.json"
    stats = ChestStats(path)
    assert stats.set(1234) == 1234
    assert stats.exists
    assert stats.add(1) == 1235
    assert ChestStats(path).total == 1235
    assert stats.set(-5) == 0


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("{kaputt")
    stats = ChestStats(path)
    assert stats.total == 0
    assert (tmp_path / "stats.broken.json").exists()


def test_config_merges_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"hotkeys": {"increment": "+"}, "interact_key": "f"}))
    config = load_config(path)
    assert config["hotkeys"]["increment"] == "+"
    assert config["hotkeys"]["decrement"] == DEFAULT_CONFIG["hotkeys"]["decrement"]
    assert config["interact_key"] == "f"
    assert config["detection"]["match_threshold"] == DEFAULT_CONFIG["detection"]["match_threshold"]


def test_default_hotkeys():
    assert DEFAULT_CONFIG["hotkeys"]["increment"] == "´"
    assert DEFAULT_CONFIG["hotkeys"]["decrement"] == "ß"
