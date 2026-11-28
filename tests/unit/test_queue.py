import asyncio

import pytest

from infrastructure.queue import AsyncDownloadQueue, DownloadJob, JobStatus


@pytest.fixture
def queue():
    return AsyncDownloadQueue()


async def test_enqueue_dequeue_marks_running_and_completed(queue):
    job = DownloadJob(job_id="job-1", user_id=111, url="https://youtu.be/x", platform="youtube")
    await queue.enqueue(job)
    assert queue.get_stats().pending_jobs == 1

    nxt = await queue.dequeue()
    assert nxt is job
    await queue.mark_running(job, asyncio.current_task())
    assert job.status is JobStatus.RUNNING
    assert queue.get_stats().running_jobs == 1

    await queue.mark_completed(job, result="/tmp/x.mp3")
    assert job.status is JobStatus.COMPLETED
    assert queue.get_stats().completed_jobs == 1
    assert queue.get_stats().running_jobs == 0


async def test_enqueue_rejects_when_full(queue):
    queue._max_size = 1
    await queue.enqueue(DownloadJob(job_id="job-1", user_id=111))
    with pytest.raises(Exception):
        await queue.enqueue(DownloadJob(job_id="job-2", user_id=111))


async def test_cancel_pending_job(queue):
    job = DownloadJob(job_id="job-1", user_id=111, url="https://youtu.be/x", platform="youtube")
    await queue.enqueue(job)
    assert await queue.cancel_job("job-1") is True
    assert job.status is JobStatus.CANCELLED
    assert queue.get_stats().pending_jobs == 0
    assert await queue.dequeue() is None


async def test_cancel_unknown_job_returns_false(queue):
    assert await queue.cancel_job("no-such-job") is False


async def test_mark_failed_records_error(queue):
    job = DownloadJob(job_id="job-1", user_id=111)
    await queue.enqueue(job)
    await queue.mark_failed(job, "boom")
    assert job.status is JobStatus.FAILED
    assert job.error == "boom"
    assert queue.get_stats().failed_jobs == 1


async def test_completed_history_is_bounded(queue):
    for i in range(1005):
        job = DownloadJob(job_id=f"job-{i}", user_id=111)
        await queue.enqueue(job)
        await queue.dequeue()
        await queue.mark_completed(job)
    assert len(queue._completed) <= 1000


async def test_get_job_finds_pending_running_and_completed(queue):
    job = DownloadJob(job_id="job-1", user_id=111)
    await queue.enqueue(job)
    assert queue.get_job("job-1") is job
    await queue.mark_completed(job)
    assert queue.get_job("job-1") is job
    assert queue.get_job("missing") is None
