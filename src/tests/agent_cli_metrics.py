#!/usr/bin/env python3
"""Measure real agent CLI calls without changing the CLI's stdout/exit contract.

Set OPENSHOT_METRICS_DIR and optionally OPENSHOT_CLI_COMMAND (a JSON argv array),
then use this script in place of openshot-cli. Default command runs ../cli.py.
Summarize with: python3 agent_cli_metrics.py --summarize DIRECTORY
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def summarize(directory):
    rows = [json.loads(line) for line in (Path(directory) / 'calls.jsonl').read_text().splitlines()]
    if not rows:
        return {'calls': 0}
    return {
        'calls': len(rows), 'errors': sum(row['exit_code'] != 0 for row in rows),
        'help_calls': sum(any(arg in ('help', '--help', '-h', 'agent') for arg in row['args']) for row in rows),
        'wall_seconds': round(max(row['started'] + row['elapsed_seconds'] for row in rows) - min(row['started'] for row in rows), 3),
        'cli_seconds_sum': round(sum(row['elapsed_seconds'] for row in rows), 3),
        'response_bytes': sum(row['stdout_bytes'] + row['stderr_bytes'] for row in rows),
        'wait_status_requests': sum((row.get('wait') or {}).get('status_requests', 0) for row in rows),
        'slowest_calls': [{'args': row['args'], 'seconds': round(row['elapsed_seconds'], 3)}
                          for row in sorted(rows, key=lambda row: -row['elapsed_seconds'])[:5]],
    }


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--summarize':
        print(json.dumps(summarize(sys.argv[2]), indent=2))
        return 0
    directory = Path(os.environ['OPENSHOT_METRICS_DIR'])
    directory.mkdir(parents=True, exist_ok=True)
    command = json.loads(os.environ.get('OPENSHOT_CLI_COMMAND', 'null')) or [sys.executable, str(Path(__file__).resolve().parents[1] / 'cli.py')]
    started, monotonic = time.time(), time.monotonic()
    result = subprocess.run(command + sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record = {'args': sys.argv[1:], 'started': started,
              'elapsed_seconds': time.monotonic() - monotonic, 'exit_code': result.returncode,
              'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr)}
    if result.returncode:
        record['error'] = result.stderr.decode('utf-8', errors='replace')[-4000:]
    try:
        payload = json.loads(result.stdout).get('result', {})
        if isinstance(payload, dict):
            record['wait'] = payload.get('wait')
            data = payload.get('data', {})
            if isinstance(data, dict):
                artifact = data.get('path')
                if artifact and Path(artifact).is_file():
                    record['artifact_bytes'] = Path(artifact).stat().st_size
                for key in ('waveforms', 'thumbnails'):
                    if key in data:
                        record[key] = data[key]
    except (ValueError, OSError):
        pass
    with (directory / 'calls.jsonl').open('a') as log:
        log.write(json.dumps(record) + '\n')
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
