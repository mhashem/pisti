"""Tests for config loading."""

from pathlib import Path

import yaml

from pisti.core.config import PistiConfig, load_config


def test_default_config():
    cfg = load_config()
    assert cfg.ollama.base_url == "http://localhost:11434"
    assert cfg.agents.coder.max_iterations == 20
    assert cfg.tools.max_read_chars == 50_000


def test_load_config_from_file(tmp_path: Path):
    config_data = {
        "ollama": {"base_url": "http://custom:1234", "timeout": 60.0},
        "agents": {"coder": {"model": "llama3", "max_iterations": 10}},
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    cfg = load_config(path=config_file)
    assert cfg.ollama.base_url == "http://custom:1234"
    assert cfg.agents.coder.model == "llama3"
    assert cfg.agents.coder.max_iterations == 10
    # Defaults preserved for unspecified fields
    assert cfg.tools.max_read_chars == 50_000


def test_load_config_missing_file():
    cfg = load_config(path=Path("/nonexistent/config.yaml"))
    assert isinstance(cfg, PistiConfig)
    assert cfg.ollama.base_url == "http://localhost:11434"
