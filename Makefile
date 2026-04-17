.PHONY: install compose ticket task task-loop qa ticket-auto task-auto task-loop-auto qa-auto tr-install format lint test coverage

install:
	uv sync --group dev

compose:
	uv run python -m ticket_ralph.compose

ticket:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make ticket TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	uv run ticket-ralph ticket $(TR_TICKET) $(TR_EXTRA)

task:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	uv run ticket-ralph task $(TR_TICKET) $(TR_EXTRA)

task-loop:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-loop TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	uv run ticket-ralph task-loop $(TR_TICKET) $(TR_EXTRA)

qa:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make qa TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	uv run ticket-ralph qa $(TR_TICKET) $(TR_EXTRA)

ticket-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make ticket-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true uv run ticket-ralph ticket $(TR_TICKET) $(TR_EXTRA)

task-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true uv run ticket-ralph task $(TR_TICKET) $(TR_EXTRA)

task-loop-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-loop-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true uv run ticket-ralph task-loop $(TR_TICKET) $(TR_EXTRA)

qa-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make qa-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true uv run ticket-ralph qa $(TR_TICKET) $(TR_EXTRA)

tr-install: compose
	mkdir -p ~/.ticket-ralph/tickets
	uv tool install --force --editable .
	mkdir -p ~/.claude/agents/
	cp agents/*.md ~/.claude/agents/
	cp scripts/hooks/*.sh ~/.claude/hooks/
	chmod +x ~/.claude/hooks/*.sh
	@echo "Installed ticket-ralph CLI, agents, and hooks"
	@echo "Usage from any repo: ticket-ralph ticket PROJ-123"

format:
	uvx ruff format src/ tests/

lint:
	uvx ruff check --fix src/ tests/

test:
	uv run pytest --cov src --cov-fail-under 80 tests/ -v
