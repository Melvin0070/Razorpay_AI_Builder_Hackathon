# LeakProof entry points. Every target runs through uv so the pinned Python and
# the locked dependency set are used in every worktree and in CI alike.
UV ?= uv
# uv needs a writable cache. Sandboxed lane agents cannot write ~/.cache, so fall
# back to a repo-local cache (gitignored) when the default is not writable.
UV_CACHE_DIR ?= $(shell touch "$(HOME)/.cache/uv/.probe" 2>/dev/null && echo "$(HOME)/.cache/uv" || echo "$(CURDIR)/.uv-cache")
export UV_CACHE_DIR

.PHONY: sync lint fmt test verify triage demo serve gen metrics throughput clean

sync:
	$(UV) sync

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test:
	$(UV) run pytest

# Deterministic. Zero network, no API key. Regenerates seeded batches, reproduces
# every published metric, and fails on any hard gate (design doc, D10 / D11).
verify:
	$(UV) run pytest
	$(UV) run python -m leakproof verify

# Opt-in LLM job. Needs ANTHROPIC_API_KEY in the environment. Resumable (D11).
triage:
	$(UV) run --extra triage python -m leakproof triage

# Emits out/demo.html, self-contained, keyless (D16).
demo:
	$(UV) run python -m leakproof demo

# FastAPI, only for the live approve / override / reject interaction (D8, D16).
serve:
	$(UV) run --extra serve python -m leakproof serve

gen:
	$(UV) run python -m leakproof gen

metrics:
	$(UV) run python -m leakproof metrics

# 10k-order batch through the deterministic path; publishes seconds (D13).
throughput:
	$(UV) run python -m leakproof throughput

clean:
	rm -rf out .pytest_cache .ruff_cache .hypothesis
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
