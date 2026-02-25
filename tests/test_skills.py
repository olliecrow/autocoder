from __future__ import annotations

from pathlib import Path

from autocoder.skills import LocalSkill, discover_local_skills, render_skills_for_prompt


def test_discover_local_skills_reads_codex_home_and_frontmatter(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    verify = codex_home / "skills" / "verify" / "SKILL.md"
    verify.parent.mkdir(parents=True, exist_ok=True)
    verify.write_text(
        "\n".join(
            [
                "---",
                "name: verify",
                "description: Verify correctness with strong evidence.",
                "---",
                "",
                "# verify",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cleanup = codex_home / "skills" / "cleanup" / "SKILL.md"
    cleanup.parent.mkdir(parents=True, exist_ok=True)
    cleanup.write_text("# cleanup\n", encoding="utf-8")

    skills = discover_local_skills(
        env={"CODEX_HOME": str(codex_home)},
        home=tmp_path / "home",
    )

    assert tuple(s.name for s in skills) == ("cleanup", "verify")
    assert skills[1].description == "Verify correctness with strong evidence."


def test_discover_local_skills_falls_back_to_home_dot_codex(tmp_path: Path) -> None:
    home = tmp_path / "home"
    plan = home / ".codex" / "skills" / "plan" / "SKILL.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\nname: plan\ndescription: Create plans.\n---\n", encoding="utf-8")

    skills = discover_local_skills(env={}, home=home)

    assert len(skills) == 1
    assert skills[0].name == "plan"
    assert skills[0].description == "Create plans."


def test_render_skills_for_prompt_limits_output() -> None:
    skills = tuple(
        LocalSkill(
            name=f"skill-{i}",
            description=f"description-{i}",
            path=Path(f"/tmp/skill-{i}/SKILL.md"),
        )
        for i in range(3)
    )

    out = render_skills_for_prompt(skills, max_items=2)

    assert "- skill-0: description-0" in out
    assert "- skill-1: description-1" in out
    assert "... plus 1 more locally available skills" in out


def test_render_skills_for_prompt_assumes_local_skills_when_empty() -> None:
    out = render_skills_for_prompt(())

    assert "Local skills are assumed to exist on this machine." in out
    assert "~/.codex/skills" in out
