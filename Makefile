.PHONY: install compose ticket task task-loop qa ticket-auto task-auto task-loop-auto qa-auto tr-install

install:
	uv sync

compose:
	uv run python -m ticket_ralph.compose

ticket:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make ticket TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	./scripts/ticket.sh $(TR_TICKET) $(TR_EXTRA)

task:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	./scripts/task.sh $(TR_TICKET) $(TR_EXTRA)

task-loop:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-loop TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	./scripts/task-loop.sh $(TR_TICKET) $(TR_EXTRA)

qa:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make qa TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	./scripts/qa.sh $(TR_TICKET) $(TR_EXTRA)

ticket-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make ticket-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true ./scripts/ticket.sh $(TR_TICKET) $(TR_EXTRA)

task-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true ./scripts/task.sh $(TR_TICKET) $(TR_EXTRA)

task-loop-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make task-loop-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true ./scripts/task-loop.sh $(TR_TICKET) $(TR_EXTRA)

qa-auto:
	@if [ -z "$(TR_TICKET)" ]; then echo "Usage: make qa-auto TR_TICKET=PROJ-123 [TR_EXTRA='extra context']"; exit 1; fi
	TR_AUTONOMOUS=true ./scripts/qa.sh $(TR_TICKET) $(TR_EXTRA)

tr-install: compose
	mkdir -p ~/.ticket-ralph/tickets
	cp -R scripts ~/.ticket-ralph/
	chmod +x ~/.ticket-ralph/scripts/*.sh ~/.ticket-ralph/scripts/hooks/*.sh
	sed "s|~/.ticket-ralph|$$HOME/.ticket-ralph|g" .claude/ticket-ralph-settings.json > ~/.ticket-ralph/settings.json
	mkdir -p ~/.claude/agents/
	cp agents/*.md ~/.claude/agents/
	cp scripts/hooks/*.sh ~/.claude/hooks/
	chmod +x ~/.claude/hooks/*.sh
	@echo "Installed to ~/.ticket-ralph/ and ~/.claude/"
	@echo "Example start workflow from any repo: ~/.ticket-ralph/scripts/ticket.sh PROJ-123"
