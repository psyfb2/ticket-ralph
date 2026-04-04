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
  for fragment in ${fragments[@]+"${fragments[@]}"}; do
    local fragment_file="$FRAGMENTS_DIR/${fragment}.md"
    if [ ! -f "$fragment_file" ]; then
      echo "ERROR: Fragment not found: $fragment_file" >&2
      exit 1
    fi
    cat "$fragment_file" >> "$output_file"
    echo "" >> "$output_file"
  done

  # --- Append agent-specific content (skip frontmatter + leading blank lines) ---
  awk 'BEGIN{n=0; body=0} /^---$/{n++; next} n>=2{if(!body && /^$/){next} body=1; print}' "$agent_fragment" >> "$output_file"

  composed_count=$((composed_count + 1))
  echo "  Built: agents/${agent_name}.md"
}

echo "Composing agents..."
echo ""

# =====================================================================
# Agent Compositions
# =====================================================================

compose_agent "tr-high-level-plan" \
  "shared/role-architect" \
  "shared/context7" \
  "shared/plan-methodology" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-high-level-plan-review" \
  "shared/role-reviewer" \
  "shared/file-conventions"

compose_agent "tr-plan" \
  "shared/role-architect" \
  "shared/context7" \
  "shared/plan-methodology" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-plan-review" \
  "shared/role-reviewer" \
  "shared/file-conventions"

compose_agent "tr-plan-fixer" \
  "shared/role-architect" \
  "shared/context7" \
  "shared/file-conventions"

compose_agent "tr-plan-confirm" \
  "shared/file-conventions"

compose_agent "tr-implementor" \
  "shared/role-engineer" \
  "shared/context7" \
  "shared/verification" \
  "shared/file-conventions" \
  "shared/progress-tracking"

compose_agent "tr-impl-review" \
  "shared/role-reviewer" \
  "shared/verification" \
  "shared/file-conventions"

compose_agent "tr-impl-review-fixer" \
  "shared/role-engineer" \
  "shared/context7" \
  "shared/verification" \
  "shared/file-conventions"

compose_agent "tr-qa" \
  "shared/role-qa" \
  "shared/verification" \
  "shared/file-conventions"

compose_agent "tr-qa-fixer" \
  "shared/role-engineer" \
  "shared/context7" \
  "shared/verification" \
  "shared/file-conventions"

echo ""
echo "Done. Composed $composed_count agents in $AGENTS_DIR/"
echo ""
echo "To install globally: cp $AGENTS_DIR/*.md ~/.claude/agents/"
echo "Add hook scripts if this has not been done already: 
cp scripts/hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
"