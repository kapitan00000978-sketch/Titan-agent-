"""Cron scheduler tests (Block 2: Hermes-class scheduled jobs)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime

from titan_agent.scheduler import CronScheduler, _matches_cron, _parse_cron


def test_parse_cron_star_and_ranges():
    parsed = _parse_cron("*/5 9 * * 1-5")
    assert parsed["minute"] == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
    assert parsed["hour"] == {9}
    assert parsed["dom"] is None
    assert parsed["month"] is None
    assert parsed["dow"] == {1, 2, 3, 4, 5}
    parsed = _parse_cron("0 9 * * 1-5")
    assert parsed["minute"] == {0}
    parsed2 = _parse_cron("30 8 * * 0,6")
    assert parsed2["dow"] == {0, 6}


def test_matches_cron():
    p = _parse_cron("0 9 * * 1")  # 09:00 on Monday
    assert _matches_cron(p, datetime(2026, 9, 21, 9, 0)) is True   # Mon 2026-09-21
    assert _matches_cron(p, datetime(2026, 9, 21, 9, 30)) is False  # wrong minute
    assert _matches_cron(p, datetime(2026, 9, 22, 9, 0)) is False   # Tuesday


def test_add_remove_toggle(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    calls = []

    async def runner(prompt, sid, mode, effort):
        calls.append((prompt, sid, mode, effort))
        return f"done:{prompt[:10]}"

    sch = CronScheduler(runner=runner, jobs_file=jobs_file, tick_seconds=0.05)
    job = sch.add_job(prompt="hello", name="t", schedule={"interval_minutes": 1}, job_id="j1")
    assert job["id"] == "j1"
    assert sch.list_jobs()[0]["name"] == "t"
    assert sch.remove_job("j1") is True
    assert sch.remove_job("nope") is False
    sch.add_job(prompt="x", job_id="j2")
    toggled = sch.toggle_job("j2")
    assert toggled["enabled"] is False
    assert sch.jobs["j2"]["enabled"] is False


def test_interval_job_fires_on_tick(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    calls = []

    async def runner(prompt, sid, mode, effort):
        calls.append(prompt)
        return "result"

    sch = CronScheduler(runner=runner, jobs_file=jobs_file, tick_seconds=0.02)
    sch.add_job(
        prompt="tick-me",
        schedule={"interval_minutes": 0.001},  # ~0.06s
        job_id="fast_job",
    )

    async def main():
        await sch.start()
        await asyncio.sleep(0.25)
        await sch.stop()

    asyncio.run(main())
    assert "tick-me" in calls
    job = sch.jobs["fast_job"]
    assert job["last_status"] == "success"
    assert job["last_result"] == "result"
    assert job["last_run"] is not None


def test_disabled_job_does_not_run(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    calls = []

    async def runner(prompt, sid, mode, effort):
        calls.append(prompt)
        return "result"

    sch = CronScheduler(runner=runner, jobs_file=jobs_file, tick_seconds=0.02)
    sch.add_job(prompt="never", schedule={"interval_minutes": 0.001}, job_id="off",
                enabled=False)

    async def main():
        await sch.start()
        await asyncio.sleep(0.15)
        await sch.stop()

    asyncio.run(main())
    assert calls == []


def test_run_now_manual(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    calls = []

    async def runner(prompt, sid, mode, effort):
        calls.append(prompt)
        return "manual-result"

    sch = CronScheduler(runner=runner, jobs_file=jobs_file, tick_seconds=0.05)
    sch.add_job(prompt="manual", job_id="m1")

    async def main():
        job = await sch.run_now("m1")
        assert job["last_result"] == "manual-result"

    asyncio.run(main())
    assert calls == ["manual"]


def test_runner_error_marks_job_failed(tmp_path):
    jobs_file = tmp_path / "jobs.json"

    async def failing_runner(prompt, sid, mode, effort):
        raise RuntimeError("boom")

    sch = CronScheduler(runner=failing_runner, jobs_file=jobs_file, tick_seconds=0.05)
    sch.add_job(prompt="x", job_id="e1")

    async def main():
        job = await sch.run_now("e1")
        assert job["last_status"] == "error"
        assert "boom" in job["last_result"]

    asyncio.run(main())


def test_jobs_json_persistence(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    calls = []

    async def runner(prompt, sid, mode, effort):
        return "ok"

    sch = CronScheduler(runner=runner, jobs_file=jobs_file)
    sch.add_job(prompt="persist me", name="P", job_id="p1")
    # Recreate from the file on disk
    sch2 = CronScheduler(runner=runner, jobs_file=jobs_file)
    assert "p1" in sch2.jobs
    assert sch2.jobs["p1"]["name"] == "P"