# Pisti

Multi-agent SDLC platform. Give it an instruction, and the Coder agent uses an LLM (via Ollama) to explore your project, plan changes, and write code using filesystem tools.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a model pulled (default: `qwen2.5-coder:7b`)

```bash
# Install and start Ollama
brew install ollama
ollama serve &
ollama pull qwen2.5-coder:7b
```

## Installation

### From source

```bash
git clone https://github.com/your-org/pisti.git
cd pisti
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

### From PyPI

```bash
pip install pisti
```

### With Homebrew

```bash
brew tap your-org/tap
brew install pisti
```

## Usage

```bash
# Run the Coder agent
pisti code "Create a FastAPI hello world endpoint"

# Specify a working directory and model
pisti code "Add unit tests" --dir ./my-project --model llama3

# Initialize a project config
pisti config init
```

## Configuration

Pisti searches for config in this order:

1. `.pisti/config.yaml` (project-local)
2. `~/.config/pisti/config.yaml` (user-global)
3. Built-in defaults

Generate a default config:

```bash
pisti config init
```

Example `.pisti/config.yaml`:

```yaml
ollama:
  base_url: http://localhost:11434
  timeout: 120.0
agents:
  coder:
    model: qwen2.5-coder:7b
    max_iterations: 20
    context_window: 8192
tools:
  max_read_chars: 50000
```

## Development

```bash
make fmt         # Format code
make lint        # Lint check
make typecheck   # mypy strict
make test        # Run tests
make all         # All of the above
```

## Publishing to PyPI

Build and upload:

```bash
pip install build twine
python -m build
twine upload dist/*
```

## Publishing a Homebrew formula

### 1. Create a tap repository

Create a GitHub repo named `homebrew-tap` under your org (e.g. `your-org/homebrew-tap`).

### 2. Create the formula

Add `Formula/pisti.rb` to the tap repo:

```ruby
class Pisti < Formula
  include Language::Python::Virtualenv

  desc "Multi-agent SDLC platform"
  homepage "https://github.com/your-org/pisti"
  url "https://files.pythonhosted.org/packages/source/p/pisti/pisti-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_OF_SDIST"
  license "MIT"

  depends_on "python@3.12"

  # Add resource blocks for each dependency.
  # Generate them with: brew python-resources pisti
  # or manually with: pip install homebrew-pypi-poet && poet pisti

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Multi-agent", shell_output("#{bin}/pisti --help")
  end
end
```

### 3. Generate dependency resources

```bash
pip install homebrew-pypi-poet
poet pisti
```

Paste the output `resource` blocks into the formula above.

### 4. Get the sdist SHA256

```bash
curl -sL https://files.pythonhosted.org/packages/source/p/pisti/pisti-0.1.0.tar.gz | shasum -a 256
```

Replace `REPLACE_WITH_SHA256_OF_SDIST` in the formula.

### 5. Test locally

```bash
brew tap your-org/tap
brew install --build-from-source pisti
pisti --help
```

### 6. Automate releases

Add a GitHub Actions workflow to your main repo that, on a new tag:

1. Builds and publishes to PyPI
2. Updates the formula SHA and URL in the tap repo

```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    tags: ["v*"]
jobs:
  pypi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
  homebrew:
    needs: pypi
    runs-on: ubuntu-latest
    steps:
      - uses: dawidd6/action-homebrew-bump-formula@v4
        with:
          token: ${{ secrets.HOMEBREW_TAP_TOKEN }}
          tap: your-org/tap
          formula: pisti
```
