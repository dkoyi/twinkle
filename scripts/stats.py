"""Summarize actual demo task results; never infer unsafe-action counts."""
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', nargs='?', default='logs')
    args = parser.parse_args()
    tasks = {}
    for path in Path(args.logs).rglob('*.jsonl'):
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') == 'task_finished':
                tasks[event.get('task_id', str(path))] = event
    print(f'Completed task runs: {len(tasks)}')
    for outcome, count in sorted(Counter(event.get('outcome', 'unknown') for event in tasks.values()).items()):
        print(f'  {outcome}: {count}')
    durations = [event['duration_s'] for event in tasks.values() if isinstance(event.get('duration_s'), (float,int))]
    if durations:
        print(f'Average task duration: {mean(durations):.1f} seconds')
    print('Unsafe-action count requires review of actual actions; it is not inferred from these logs.')


if __name__ == '__main__':
    main()
