"""
 @file
 @brief Client-side export waiting; never blocks the editor's Qt event loop.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """
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
