"""Tests for ticket_ralph.compose."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.compose import (
    compose_agent,
    discover_variables,
    file_to_var_name,
    main,
    parse_frontmatter,
    preprocess_indented_vars,
    resolve_variables,
)


@dataclass
class MainDirs:
    """Filesystem layout used by `main()` tests."""

    fragments_dir: Path
    agents_fragment_dir: Path
    shared_dir: Path
    sub_shared_dir: Path
    output_dir: Path


@pytest.fixture
def main_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainDirs:
    """Scaffold the fragments/agents/shared/output dirs and patch module paths.

    Patches the six module-level path constants used by `main()` so each test
    operates inside its own ``tmp_path``. ``shared_dir`` and
    ``agents_fragment_dir`` are pre-created; ``output_dir`` is left absent so
    tests can assert `main()` creates it (or pre-populate it to test cleanup).
    """
    fragments_dir = tmp_path / "fragments"
    agents_fragment_dir = fragments_dir / "agents"
    shared_dir = fragments_dir / "shared"
    sub_shared_dir = shared_dir / "shared"
    output_dir = tmp_path / "agents"

    agents_fragment_dir.mkdir(parents=True)
    shared_dir.mkdir(parents=True)

    monkeypatch.setattr("ticket_ralph.compose.PROJECT_DIR", tmp_path)
    monkeypatch.setattr("ticket_ralph.compose.FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(
        "ticket_ralph.compose.AGENTS_FRAGMENT_DIR", agents_fragment_dir
    )
    monkeypatch.setattr("ticket_ralph.compose.SHARED_DIR", shared_dir)
    monkeypatch.setattr("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir)
    monkeypatch.setattr("ticket_ralph.compose.OUTPUT_DIR", output_dir)

    return MainDirs(
        fragments_dir=fragments_dir,
        agents_fragment_dir=agents_fragment_dir,
        shared_dir=shared_dir,
        sub_shared_dir=sub_shared_dir,
        output_dir=output_dir,
    )


class TestPreprocessIndentedVars:
    def test_indented_var_gets_indent_filter(self) -> None:
        template = "items:\n    {{ my_list }}\n"
        result = preprocess_indented_vars(template)
        assert "{{ my_list | indent(4, first=False) }}" in result

    def test_non_indented_var_unchanged(self) -> None:
        template = "{{ my_var }}\n"
        result = preprocess_indented_vars(template)
        assert result == template

    def test_inline_var_unchanged(self) -> None:
        template = "prefix {{ my_var }} suffix\n"
        result = preprocess_indented_vars(template)
        assert result == template

    def test_tabs_as_indentation(self) -> None:
        template = "items:\n\t{{ my_list }}\n"
        result = preprocess_indented_vars(template)
        assert "{{ my_list | indent(1, first=False) }}" in result

    def test_multiple_indented_vars(self) -> None:
        template = "a:\n  {{ var1 }}\nb:\n    {{ var2 }}\n"
        result = preprocess_indented_vars(template)
        assert "{{ var1 | indent(2, first=False) }}" in result
        assert "{{ var2 | indent(4, first=False) }}" in result

    def test_no_vars(self) -> None:
        template = "just plain text\n  no vars here\n"
        result = preprocess_indented_vars(template)
        assert result == template

    def test_trailing_whitespace_on_var_line(self) -> None:
        template = "  {{ my_var }}   \n"
        result = preprocess_indented_vars(template)
        assert "{{ my_var | indent(2, first=False) }}" in result

    def test_empty_string(self) -> None:
        assert preprocess_indented_vars("") == ""


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        text = "---\nname: my-agent\nother: value\n---\nBody content here."
        frontmatter, body, name = parse_frontmatter(text)
        assert name == "my-agent"
        assert "name: my-agent" in frontmatter
        assert "---" in frontmatter
        assert body == "Body content here."

    def test_missing_delimiters(self) -> None:
        text = "no delimiters at all"
        with pytest.raises(ValueError, match="missing frontmatter"):
            parse_frontmatter(text)

    def test_single_delimiter(self) -> None:
        text = "---\nname: agent\nno closing delimiter"
        with pytest.raises(ValueError, match="missing frontmatter"):
            parse_frontmatter(text)

    def test_missing_name_field(self) -> None:
        text = "---\ntitle: not-a-name\n---\nBody."
        with pytest.raises(ValueError, match="missing 'name' field"):
            parse_frontmatter(text)

    def test_multiline_body(self) -> None:
        text = "---\nname: agent\n---\nLine one\nLine two\nLine three"
        frontmatter, body, name = parse_frontmatter(text)
        assert name == "agent"
        assert "Line one\nLine two\nLine three" == body

    def test_name_with_surrounding_whitespace(self) -> None:
        text = "---\nname:   spaced-name   \n---\nBody."
        _, _, name = parse_frontmatter(text)
        assert name == "spaced-name"

    def test_empty_body(self) -> None:
        text = "---\nname: agent\n---\n"
        frontmatter, body, name = parse_frontmatter(text)
        assert name == "agent"
        assert body == ""

    def test_extra_delimiters_in_body(self) -> None:
        text = "---\nname: agent\n---\nBody with --- inside"
        frontmatter, body, name = parse_frontmatter(text)
        assert name == "agent"
        assert "---" in body


class TestFileToVarName:
    def test_hyphens_to_underscores(self) -> None:
        assert file_to_var_name(Path("my-file-name.md")) == "my_file_name"

    def test_no_hyphens(self) -> None:
        assert file_to_var_name(Path("simple.md")) == "simple"

    def test_strips_extension(self) -> None:
        assert file_to_var_name(Path("data.txt")) == "data"

    def test_already_underscored(self) -> None:
        assert file_to_var_name(Path("already_underscored.md")) == "already_underscored"

    def test_nested_path(self) -> None:
        assert file_to_var_name(Path("dir/sub/my-file.md")) == "my_file"


class TestDiscoverVariables:
    def test_discovers_from_shared_dir(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        shared_dir.mkdir(parents=True)

        (shared_dir / "my-var.md").write_text("shared content")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
        ):
            variables = discover_variables()

        assert variables == {"my_var": "shared content"}

    def test_discovers_from_sub_shared_dir(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        sub_shared_dir.mkdir(parents=True)

        (sub_shared_dir / "inner-var.md").write_text("inner content")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
        ):
            variables = discover_variables()

        assert variables == {"inner_var": "inner content"}

    def test_discovers_from_both_dirs(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        sub_shared_dir.mkdir(parents=True)

        (shared_dir / "outer.md").write_text("outer content")
        (sub_shared_dir / "inner.md").write_text("inner content")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
        ):
            variables = discover_variables()

        assert variables == {
            "outer": "outer content",
            "inner": "inner content",
        }

    def test_name_conflict_raises(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        sub_shared_dir.mkdir(parents=True)

        (shared_dir / "duplicate.md").write_text("outer")
        (sub_shared_dir / "duplicate.md").write_text("inner")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
            pytest.raises(ValueError, match="Variable name conflict.*duplicate"),
        ):
            discover_variables()

    def test_no_dirs_exist(self, tmp_path: Path) -> None:
        nonexistent_shared = tmp_path / "nonexistent" / "shared"
        nonexistent_sub = tmp_path / "nonexistent" / "shared" / "shared"

        with (
            patch("ticket_ralph.compose.SHARED_DIR", nonexistent_shared),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", nonexistent_sub),
        ):
            variables = discover_variables()

        assert variables == {}

    def test_strips_whitespace_from_content(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        shared_dir.mkdir(parents=True)

        (shared_dir / "padded.md").write_text("  content with whitespace  \n\n")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
        ):
            variables = discover_variables()

        assert variables["padded"] == "content with whitespace"

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "fragments" / "shared"
        sub_shared_dir = shared_dir / "shared"
        shared_dir.mkdir(parents=True)

        (shared_dir / "valid.md").write_text("markdown content")
        (shared_dir / "ignored.txt").write_text("text content")
        (shared_dir / "ignored.py").write_text("python content")

        with (
            patch("ticket_ralph.compose.SHARED_DIR", shared_dir),
            patch("ticket_ralph.compose.SUB_SHARED_DIR", sub_shared_dir),
        ):
            variables = discover_variables()

        assert list(variables.keys()) == ["valid"]


class TestResolveVariables:
    def test_no_references(self) -> None:
        raw = {"greeting": "hello", "name": "world"}
        result = resolve_variables(raw)
        assert result == {"greeting": "hello", "name": "world"}

    def test_simple_reference(self) -> None:
        raw = {"greeting": "hello", "message": "{{ greeting }} world"}
        result = resolve_variables(raw)
        assert result["message"] == "hello world"

    def test_nested_references(self) -> None:
        raw = {
            "a": "base",
            "b": "{{ a }}-extended",
            "c": "{{ b }}-final",
        }
        result = resolve_variables(raw)
        assert result["c"] == "base-extended-final"

    def test_unresolvable_reference_raises(self) -> None:
        raw = {"broken": "{{ nonexistent }}"}
        with pytest.raises(Exception):
            resolve_variables(raw)

    def test_circular_reference_raises(self) -> None:
        raw = {"a": "{{ b }}", "b": "{{ a }}"}
        with pytest.raises(Exception):
            resolve_variables(raw)

    def test_indented_variable_gets_indent_filter(self) -> None:
        raw = {
            "inner": "line1\nline2\nline3",
            "outer": "items:\n  {{ inner }}",
        }
        result = resolve_variables(raw)
        assert result["outer"] == "items:\n  line1\n  line2\n  line3"

    def test_already_resolved_values_unchanged(self) -> None:
        raw = {"static": "no templates here"}
        result = resolve_variables(raw)
        assert result["static"] == "no templates here"

    def test_unresolved_after_max_depth_raises(self) -> None:
        # Build a chain deeper than MAX_RESOLVE_DEPTH (5) so it never fully
        # resolves. Each pass resolves one level, so depth 7 exceeds 5 passes.
        # With MAX_RESOLVE_DEPTH=5, after 5 passes some may still have {{ }}.
        # However, Jinja2 resolves references immediately if the variable is
        # already resolved, so each pass resolves one more level. With 8 vars
        # (chain of 7 hops), 5 passes should leave v7 unresolved.
        # Actually, let's be more careful: each pass resolves ALL vars that
        # reference already-resolved vars. So pass 1 resolves v1, pass 2
        # resolves v2, etc. After 5 passes, v5 is resolved but v6/v7 are not.
        # Actually on each pass, all values are rendered, so v1 gets resolved
        # on pass 1 (because v0 has no {{). Then on pass 2, v2 resolves
        # (because v1 was resolved on pass 1). This means after 5 passes,
        # v5 resolves. v6 still has {{ v5 }} which is now resolved, but that
        # rendering happens in pass 6 which doesn't exist. So v6 would still
        # have {{ v5 }} -- wait, no. On pass 5, v5 gets resolved. In the SAME
        # pass 5, v6 = {{ v5 }} is also rendered with the updated variables
        # dict where v5 is now resolved. So v6 resolves in pass 5 too.
        #
        # Actually the code updates variables[key] = rendered inside the loop,
        # so within a single pass, later keys can see earlier updates. Since
        # dict iteration order is insertion order, v6 is rendered after v5 in
        # the same pass, so v6 sees the resolved v5.
        #
        # This means even deeply nested chains resolve quickly. We need a
        # different approach: use a pattern that Jinja2 cannot resolve in a
        # single pass because the {{ }} literal persists.
        #
        # The simplest approach: create a variable whose value STILL contains
        # {{ after rendering (e.g., by using Jinja2 raw blocks or by having
        # a variable that renders to {{ x }}).
        # Actually the easiest test: just mock MAX_RESOLVE_DEPTH to 0.
        with patch("ticket_ralph.compose.MAX_RESOLVE_DEPTH", 0):
            with pytest.raises(ValueError, match="Unresolved template reference"):
                resolve_variables({"a": "value", "b": "{{ a }}"})


class TestComposeAgent:
    def test_renders_and_writes_output(self, tmp_path: Path) -> None:
        agent_fragment = tmp_path / "agent.md"
        agent_fragment.write_text("---\nname: test-agent\n---\nHello {{ greeting }}!")

        output_dir = tmp_path / "agents"
        output_dir.mkdir()

        with patch("ticket_ralph.compose.OUTPUT_DIR", output_dir):
            name = compose_agent(agent_fragment, {"greeting": "world"})

        assert name == "test-agent"
        output_file = output_dir / "test-agent.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert "Hello world!" in content
        assert "---" in content
        assert "name: test-agent" in content

    def test_preserves_frontmatter_in_output(self, tmp_path: Path) -> None:
        agent_fragment = tmp_path / "agent.md"
        agent_fragment.write_text(
            "---\nname: my-agent\ndescription: A test agent\n---\nBody text."
        )

        output_dir = tmp_path / "agents"
        output_dir.mkdir()

        with patch("ticket_ralph.compose.OUTPUT_DIR", output_dir):
            compose_agent(agent_fragment, {})

        content = (output_dir / "my-agent.md").read_text()
        assert content.startswith(
            "---\nname: my-agent\ndescription: A test agent\n---\n"
        )

    def test_indented_variable_in_body(self, tmp_path: Path) -> None:
        agent_fragment = tmp_path / "agent.md"
        agent_fragment.write_text(
            "---\nname: indent-agent\n---\nconfig:\n  {{ items }}"
        )

        output_dir = tmp_path / "agents"
        output_dir.mkdir()

        with patch("ticket_ralph.compose.OUTPUT_DIR", output_dir):
            compose_agent(agent_fragment, {"items": "a\nb\nc"})

        content = (output_dir / "indent-agent.md").read_text()
        # Body should have indented multi-line substitution
        assert "  a\n  b\n  c" in content

    def test_missing_variable_raises(self, tmp_path: Path) -> None:
        agent_fragment = tmp_path / "agent.md"
        agent_fragment.write_text("---\nname: broken-agent\n---\n{{ undefined_var }}")

        output_dir = tmp_path / "agents"
        output_dir.mkdir()

        with patch("ticket_ralph.compose.OUTPUT_DIR", output_dir):
            with pytest.raises(Exception):
                compose_agent(agent_fragment, {})

    def test_frontmatter_is_templated(self, tmp_path: Path) -> None:
        agent_fragment = tmp_path / "agent.md"
        agent_fragment.write_text(
            "---\nname: tmpl-agent\nmodel: base{{ suffix }}\n---\nBody."
        )

        output_dir = tmp_path / "agents"
        output_dir.mkdir()

        with patch("ticket_ralph.compose.OUTPUT_DIR", output_dir):
            compose_agent(agent_fragment, {"suffix": "[1m]"})

        content = (output_dir / "tmpl-agent.md").read_text()
        assert "model: base[1m]" in content


class TestMain:
    def test_happy_path(
        self, main_dirs: MainDirs, capsys: pytest.CaptureFixture
    ) -> None:
        (main_dirs.shared_dir / "greeting.md").write_text("Hello from shared")
        (main_dirs.agents_fragment_dir / "my-agent.md").write_text(
            "---\nname: my-agent\n---\n{{ greeting }}"
        )

        main()

        agent_file = main_dirs.output_dir / "my-agent.md"
        assert agent_file.exists()
        assert "Hello from shared" in agent_file.read_text()

        captured = capsys.readouterr()
        assert "Composing agents..." in captured.out
        assert "Built: agents/my-agent.md" in captured.out
        assert "Done. Composed 1 agents" in captured.out

    def test_cleans_existing_output_dir(self, main_dirs: MainDirs) -> None:
        main_dirs.output_dir.mkdir(parents=True)
        stale_file = main_dirs.output_dir / "stale-agent.md"
        stale_file.write_text("stale content")

        (main_dirs.agents_fragment_dir / "fresh.md").write_text(
            "---\nname: fresh\n---\nFresh body."
        )

        main()

        assert not stale_file.exists()
        assert (main_dirs.output_dir / "fresh.md").exists()

    def test_no_agent_fragments_exits(self, main_dirs: MainDirs) -> None:
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_compose_error_exits(
        self, main_dirs: MainDirs, capsys: pytest.CaptureFixture
    ) -> None:
        (main_dirs.agents_fragment_dir / "bad-agent.md").write_text(
            "---\nname: bad-agent\n---\n{{ undefined_var }}"
        )

        with pytest.raises(SystemExit, match="1"):
            main()

        captured = capsys.readouterr()
        assert "ERROR composing bad-agent.md" in captured.err

    def test_multiple_agents(
        self, main_dirs: MainDirs, capsys: pytest.CaptureFixture
    ) -> None:
        (main_dirs.shared_dir / "role.md").write_text("You are helpful")

        (main_dirs.agents_fragment_dir / "agent-a.md").write_text(
            "---\nname: agent-a\n---\n{{ role }} A"
        )
        (main_dirs.agents_fragment_dir / "agent-b.md").write_text(
            "---\nname: agent-b\n---\n{{ role }} B"
        )

        main()

        assert "You are helpful A" in (main_dirs.output_dir / "agent-a.md").read_text()
        assert "You are helpful B" in (main_dirs.output_dir / "agent-b.md").read_text()

        captured = capsys.readouterr()
        assert "Composed 2 agents" in captured.out

    def test_output_dir_created_when_absent(self, main_dirs: MainDirs) -> None:
        (main_dirs.agents_fragment_dir / "simple.md").write_text(
            "---\nname: simple\n---\nBody."
        )
        assert not main_dirs.output_dir.exists()

        main()

        assert main_dirs.output_dir.exists()
        assert (main_dirs.output_dir / "simple.md").exists()

    def test_reviewer_context_suffix_defaults_empty(
        self, main_dirs: MainDirs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (main_dirs.agents_fragment_dir / "reviewer.md").write_text(
            "---\n"
            "name: reviewer\n"
            "model: claude-sonnet-4-6{{ reviewer_context_suffix }}\n"
            "---\nBody."
        )
        monkeypatch.delenv("TR_REVIEWER_LONG_CONTEXT", raising=False)

        main()

        content = (main_dirs.output_dir / "reviewer.md").read_text()
        assert "model: claude-sonnet-4-6\n" in content
        assert "[1m]" not in content

    def test_reviewer_context_suffix_enabled(
        self, main_dirs: MainDirs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (main_dirs.agents_fragment_dir / "reviewer.md").write_text(
            "---\n"
            "name: reviewer\n"
            "model: claude-sonnet-4-6{{ reviewer_context_suffix }}\n"
            "---\nBody."
        )
        # Mixed case verifies the case-insensitive parse.
        monkeypatch.setenv("TR_REVIEWER_LONG_CONTEXT", "TRUE")

        main()

        content = (main_dirs.output_dir / "reviewer.md").read_text()
        assert "model: claude-sonnet-4-6[1m]" in content

    def test_reserved_compose_time_name_collision_raises(
        self, main_dirs: MainDirs
    ) -> None:
        (main_dirs.shared_dir / "reviewer-context-suffix.md").write_text("x")
        (main_dirs.agents_fragment_dir / "any.md").write_text(
            "---\nname: any\n---\nBody."
        )

        with pytest.raises(ValueError, match="reviewer_context_suffix"):
            main()

    def test_nested_variable_resolution(self, main_dirs: MainDirs) -> None:
        # Sub-shared provides base, shared references sub-shared.
        main_dirs.sub_shared_dir.mkdir(parents=True)
        (main_dirs.sub_shared_dir / "base.md").write_text("BASE")
        (main_dirs.shared_dir / "extended.md").write_text("{{ base }}-EXTENDED")

        (main_dirs.agents_fragment_dir / "agent.md").write_text(
            "---\nname: nested\n---\nResult: {{ extended }}"
        )

        main()

        content = (main_dirs.output_dir / "nested.md").read_text()
        assert "Result: BASE-EXTENDED" in content
