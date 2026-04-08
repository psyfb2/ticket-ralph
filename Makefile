.PHONY: install compose ticket tr-install

install:
	uv sync

compose:
	uv run python -m ticket_ralph.compose

ticket:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make ticket TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	./scripts/ticket.sh $(TR_TICKET) $(TR_EXTRA)

tr-install: compose
	cp agents/*.md ~/.claude/agents/
	cp scripts/hooks/*.sh ~/.claude/hooks/
	chmod +x ~/.claude/hooks/*.sh
	@echo "Installed agents and hooks to ~/.claude/"
