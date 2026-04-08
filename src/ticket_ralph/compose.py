#!/usr/bin/env python3
"""Assembles agent .md files from fragments using Jinja2 templating.

Reads fragment files from fragments/ and resolves {{ variable }} references
to produce complete agent files in agents/. Variables are auto-discovered
from shared fragment filenames (hyphens become underscores).

Usage: uv run -m ticket_ralph.compose
"""

import re
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, StrictUndefined

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
FRAGMENTS_DIR = PROJECT_DIR / "fragments"
AGENTS_FRAGMENT_DIR = FRAGMENTS_DIR / "agents"
SHARED_DIR = FRAGMENTS_DIR / "shared"
SUB_SHARED_DIR = SHARED_DIR / "shared"
OUTPUT_DIR = PROJECT_DIR / "agents"

FRONTMATTER_DELIM = "---"
MAX_RESOLVE_DEPTH = 5


def parse_frontmatter(text: str) -> tuple[str, str, str]:
    """Split a fragment into (frontmatter_block, body, agent_name).

    Frontmatter is the YAML block between the first pair of --- delimiters.
    The agent name is extracted from the 'name:' field within the frontmatter.
    """
    lines = text.split("\n")

    # Find the two --- delimiters
    delim_indices = [i for i, line in enumerate(lines) if line.strip() == FRONTMATTER_DELIM]
    if len(delim_indices) < 2:
        raise ValueError("Fragment missing frontmatter (need two --- delimiters)")

    start, end = delim_indices[0], delim_indices[1]
    frontmatter_lines = lines[start : end + 1]
    body_lines = lines[end + 1 :]

    # Extract name from frontmatter
    name = None
    for line in frontmatter_lines:
        match = re.match(r"^name:\s*(.+)$", line)
        if match:
            name = match.group(1).strip()
            break

    if not name:
        raise ValueError("Fragment frontmatter missing 'name' field")

    frontmatter = "\n".join(frontmatter_lines)
    body = "\n".join(body_lines)
    return frontmatter, body, name


def file_to_var_name(path: Path) -> str:
    """Derive a variable name from a fragment filename.

    e.g. prd-progress-input.md -> prd_progress_input
    """
    return path.stem.replace("-", "_")


def discover_variables() -> dict[str, str]:
    """Auto-discover shared fragments and build a variable_name -> content map."""
    variables: dict[str, str] = {}

    for directory in [SUB_SHARED_DIR, SHARED_DIR]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            var_name = file_to_var_name(path)
            variables[var_name] = path.read_text().strip()

    return variables


def resolve_variables(raw_variables: dict[str, str]) -> dict[str, str]:
    """Iteratively render variable values through Jinja2 to resolve nesting."""
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    variables = dict(raw_variables)

    for _ in range(MAX_RESOLVE_DEPTH):
        changed = False
        for key, value in variables.items():
            if "{{" not in value:
                continue
            rendered = env.from_string(value).render(variables)
            if rendered != value:
                variables[key] = rendered
                changed = True
        if not changed:
            break

    # Verify all references resolved
    for key, value in variables.items():
        if "{{" in value:
            raise ValueError(
                f"Unresolved template reference in variable '{key}' after "
                f"{MAX_RESOLVE_DEPTH} passes: {value[:100]}"
            )

    return variables


def compose_agent(agent_path: Path, variables: dict[str, str]) -> str:
    """Compose a single agent file and write it to the output directory.

    Returns the agent name.
    """
    text = agent_path.read_text()
    frontmatter, body, name = parse_frontmatter(text)

    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    rendered_body = env.from_string(body).render(variables)

    output_path = OUTPUT_DIR / f"{name}.md"
    output_path.write_text(frontmatter + "\n" + rendered_body)

    return name


def main() -> None:
    # Clean and recreate output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Discover and resolve shared variables
    raw_variables = discover_variables()
    variables = resolve_variables(raw_variables)

    # Compose each agent
    agent_paths = sorted(AGENTS_FRAGMENT_DIR.glob("*.md"))
    if not agent_paths:
        print("ERROR: No agent fragments found in", AGENTS_FRAGMENT_DIR, file=sys.stderr)
        sys.exit(1)

    print("Composing agents...\n")

    for agent_path in agent_paths:
        try:
            name = compose_agent(agent_path, variables)
            print(f"  Built: agents/{name}.md")
        except Exception as e:
            print(f"ERROR composing {agent_path.name}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"\nDone. Composed {len(agent_paths)} agents in {OUTPUT_DIR}/")
    print(f"\nTo install globally: cp {OUTPUT_DIR}/*.md ~/.claude/agents/")
    print(
        "Add hook scripts if this has not been done already:\n"
        "cp scripts/hooks/*.sh ~/.claude/hooks/\n"
        "chmod +x ~/.claude/hooks/*.sh"
    )


if __name__ == "__main__":
    main()
