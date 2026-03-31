#!/usr/bin/env bash
# compose.sh — Assembles agent .md files from fragments.
#
# Reads fragment files from fragments/ and concatenates them to produce
# complete agent files in agents/. Each agent is a combination of shared
# fragments (reusable across agents) and an agent-specific fragment
# (unique instructions + frontmatter).
#
# Usage: ./scripts/compose.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRAGMENTS_DIR="$PROJECT_DIR/fragments"
AGENTS_DIR="$PROJECT_DIR/agents"

# Clean and recreate agents output directory
rm -rf "$AGENTS_DIR"
mkdir -p "$AGENTS_DIR"

composed_count=0

compose_agent() {
  local agent_name="$1"
  shift
  local fragments=("$@")

  local output_file="$AGENTS_DIR/${agent_name}.md"
  # Fragment files don't have the tr- prefix
  local fragment_name="${agent_name#tr-}"
  local agent_fragment="$FRAGMENTS_DIR/agents/${fragment_name}.md"

  # --- Extract frontmatter from the agent-specific fragment ---
  if [ ! -f "$agent_fragment" ]; then
    echo "ERROR: Agent fragment not found: $agent_fragment" >&2
    exit 1
  fi

  # Copy frontmatter (lines between first --- and second ---)
  awk '/^---$/{n++} n==1; n==2{print; exit}' "$agent_fragment" > "$output_file"
  echo "" >> "$output_file"

  # --- Concatenate shared fragments ---
  for fragment in "${fragments[@]}"; do
    local fragment_file="$FRAGMENTS_DIR/${fragment}.md"
    if [ ! -f "$fragment_file" ]; then
      echo "ERROR: Fragment not found: $fragment_file" >&2
      exit 1
    fi
    cat "$fragment_file" >> "$output_file"
    echo "" >> "$output_file"
  done

  # --- Append agent-specific content (skip frontmatter) ---
  awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$agent_fragment" >> "$output_file"

  composed_count=$((composed_count + 1))
  echo "  Built: agents/${agent_name}.md"
}

echo "Composing agents..."
echo ""

# =====================================================================
# Agent Compositions
# =====================================================================

compose_agent "tr-git-hygiene" \
  "shared/preamble" \
  "shared/git-ops"

compose_agent "tr-high-level-plan" \
  "shared/preamble" \
  "shared/role-architect" \
  "shared/solid" \
  "shared/context7" \
  "shared/jira-ops" \
  "shared/git-ops" \
  "shared/plan-methodology" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-high-level-plan-review" \
  "shared/preamble" \
  "shared/role-reviewer" \
  "shared/solid" \
  "shared/file-conventions"

compose_agent "tr-high-level-plan-fixer" \
  "shared/preamble" \
  "shared/role-architect" \
  "shared/solid" \
  "shared/context7" \
  "shared/jira-ops" \
  "shared/file-conventions"

compose_agent "tr-high-level-plan-confirm" \
  "shared/preamble" \
  "shared/jira-ops" \
  "shared/file-conventions"

compose_agent "tr-plan" \
  "shared/preamble" \
  "shared/role-architect" \
  "shared/solid" \
  "shared/context7" \
  "shared/jira-ops" \
  "shared/git-ops" \
  "shared/plan-methodology" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-plan-review" \
  "shared/preamble" \
  "shared/role-reviewer" \
  "shared/solid" \
  "shared/file-conventions"

compose_agent "tr-plan-fixer" \
  "shared/preamble" \
  "shared/role-architect" \
  "shared/solid" \
  "shared/context7" \
  "shared/jira-ops" \
  "shared/file-conventions"

compose_agent "tr-plan-confirm" \
  "shared/preamble" \
  "shared/jira-ops" \
  "shared/file-conventions"

compose_agent "tr-implementor" \
  "shared/preamble" \
  "shared/role-engineer" \
  "shared/solid" \
  "shared/context7" \
  "shared/jira-ops" \
  "shared/git-ops" \
  "shared/verification" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-impl-review" \
  "shared/preamble" \
  "shared/role-reviewer" \
  "shared/solid" \
  "shared/verification" \
  "shared/file-conventions"

compose_agent "tr-impl-review-fixer" \
  "shared/preamble" \
  "shared/role-engineer" \
  "shared/solid" \
  "shared/context7" \
  "shared/verification" \
  "shared/jira-ops" \
  "shared/file-conventions"

compose_agent "tr-qa" \
  "shared/preamble" \
  "shared/role-qa" \
  "shared/jira-ops" \
  "shared/git-ops" \
  "shared/verification" \
  "shared/file-conventions"

compose_agent "tr-qa-fixer" \
  "shared/preamble" \
  "shared/role-engineer" \
  "shared/solid" \
  "shared/context7" \
  "shared/verification" \
  "shared/file-conventions"

echo ""
echo "Done. Composed $composed_count agents in $AGENTS_DIR/"
echo ""
echo "To install globally: cp $AGENTS_DIR/*.md ~/.claude/agents/"
