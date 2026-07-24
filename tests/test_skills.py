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


def test_discover_local_skills_includes_project_skills(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    skill = project_root / ".agents" / "skills" / "release" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: release\ndescription: Publish a verified release.\n---\n",
        encoding="utf-8",
    )

    skills = discover_local_skills(
        env={},
        home=tmp_path / "home",
        project_root=project_root,
    )

    assert tuple(item.name for item in skills) == ("release",)


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


def test_render_skills_for_prompt_reports_empty_catalog() -> None:
    out = render_skills_for_prompt(())

    assert out == "- No project or local skills were discovered for this run."
