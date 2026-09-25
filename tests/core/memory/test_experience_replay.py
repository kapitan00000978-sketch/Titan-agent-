from pathlib import Path
from titan_agent.core.memory.experience_replay import ExperienceReplayEngine


def test_experience_replay_record_and_query(tmp_path):
    db_file = tmp_path / "test_exp.db"
    replay = ExperienceReplayEngine(db_path=db_file)

    err = "ModuleNotFoundError: No module named 'psycopg2'"
    solution = "Run 'pip install psycopg2-binary' to install PostgreSQL driver."
    diagnosis = "Missing compiled postgres client library."

    # Record experience
    ep = replay.record_experience(
        error_text=err,
        resolution=solution,
        diagnosis=diagnosis,
        error_type="ModuleNotFoundError",
    )
    assert ep.id > 0
    assert ep.success_count == 1

    # Query with exact or similar error
    match = replay.query_experience(err)
    assert match is not None
    assert match.resolution == solution
    assert "EPISODIC EXPERIENCE MATCH" in match.format_hint()
    assert "pip install psycopg2-binary" in match.format_hint()


def test_experience_replay_increments_success_count(tmp_path):
    db_file = tmp_path / "test_exp_count.db"
    replay = ExperienceReplayEngine(db_path=db_file)

    err = "SyntaxError: invalid syntax in line 12"
    solution = "Add missing colon at the end of if condition."

    replay.record_experience(err, solution)
    # Record again on same error
    ep2 = replay.record_experience(err, solution)
    assert ep2.success_count == 2


def test_experience_replay_miss_on_unknown_error(tmp_path):
    replay = ExperienceReplayEngine(db_path=tmp_path / "test_miss.db")
    res = replay.query_experience("ZeroDivisionError: division by zero in custom calculation")
    assert res is None
