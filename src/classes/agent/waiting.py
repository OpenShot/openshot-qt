"""Client-side export waiting; never blocks the editor's Qt event loop."""
import time

from .protocol import CommandError


def wait_for_export(record, result, request, request_timeout, wait_timeout):
    started = time.monotonic()
    deadline = started + wait_timeout
    polls = 0
    while True:
        job = result['data']
        state = job['state']
        metrics = {'seconds': round(time.monotonic() - started, 3), 'status_requests': polls}
        if state == 'completed':
            result['wait'] = metrics
            return result
        if state in ('failed', 'cancelled'):
            raise CommandError('export_' + state, job.get('error') or 'Export ' + state,
                               dict(job, wait=metrics))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CommandError('wait_timeout', 'Export is still running. Inspect with export status {} --wait; do not start it again.'.format(job['job_id']),
                               dict(job, wait=metrics))
        time.sleep(min(0.5, remaining))
        remaining = deadline - time.monotonic()
        if remaining > 0:
            polls += 1
            try:
                result = request(record, 'export.status', {'job_id': job['job_id']}, min(request_timeout, remaining))
            except CommandError as exc:
                raise CommandError(exc.code, str(exc) + ' Resume with export status {} --wait; do not start another export.'.format(job['job_id']),
                                   dict(job, cause=exc.details, wait={'seconds': round(time.monotonic()-started, 3), 'status_requests': polls}))
