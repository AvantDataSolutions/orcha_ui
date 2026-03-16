from __future__ import annotations

from datetime import datetime as dt

def format_dt(time: dt | None) -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S') if time else 'N/A'


def summarise_run_times(run_times: list[dict]) -> list[dict]:
    """Summarise run_times by grouping by module_idk and aggregating times."""
    if not run_times:
        return []

    # Group by module_idk
    grouped = {}
    for rt in run_times:
        module_idk = rt.get('module_idk', 'unknown')
        if module_idk not in grouped:
            grouped[module_idk] = {
                'module_idk': module_idk,
                'module_type': rt.get('module_type', 'N/A'),
                'module_entity': rt.get('module_entity', 'N/A'),
                'start_times': [],
                'end_times': [],
                'durations': [],
                'min_duration': None,
                'avg_duration': None,
                'max_duration': None,
                'retry_count': 0,
                'retry_exceptions': [],
                'count': 0
            }
        grouped[module_idk]['start_times'].append(rt.get('start_time_posix', 0))
        grouped[module_idk]['end_times'].append(rt.get('end_time_posix', 0))
        grouped[module_idk]['durations'].append(rt.get('duration_seconds', 0))
        grouped[module_idk]['count'] += 1
        grouped[module_idk]['retry_count'] += rt.get('retry_count', 0)
        grouped[module_idk]['retry_exceptions'].extend(rt.get('retry_exceptions', []))

    # Aggregate and sort
    summary = []
    for module_idk, data in grouped.items():
        min_start = min(data['start_times'])
        max_end = max(data['end_times'])
        total_duration = sum(data['durations'])
        min_duration = min(data['durations'])
        avg_duration = total_duration / data['count'] if data['count'] > 0 else 0
        max_duration = max(data['durations'])
        summary.append({
            'module_idk': module_idk,
            'module_type': data['module_type'],
            'module_entity': data['module_entity'],
            'min_start_time': dt.fromtimestamp(min_start).strftime('%Y-%m-%d %H:%M:%S'),
            'max_end_time': dt.fromtimestamp(max_end).strftime('%Y-%m-%d %H:%M:%S'),
            'total_duration_seconds': round(total_duration, 3),
            'min_duration_seconds': round(min_duration, 3),
            'avg_duration_seconds': round(avg_duration, 3),
            'max_duration_seconds': round(max_duration, 3),
            'run_count': data['count'],
            'min_start_posix': min_start  # for sorting
        })
        if data['retry_count'] > 0:
            summary[-1]['retry_count'] = data['retry_count']
            summary[-1]['retry_exceptions'] = data['retry_exceptions']

    # Sort by min start time
    summary.sort(key=lambda x: x['min_start_posix'])
    return summary


def summarise_run_output(run_output: dict) -> dict:
    """
    This returns output with the runtimes summarised. Returns a copy
    as it removes the raw run_times.
    """
    if 'run_times' not in run_output:
        return run_output

    output_copy = run_output.copy()
    output_copy['run_times_summary'] = summarise_run_times(run_output['run_times'])
    output_copy.pop('run_times', None)  # Remove raw run_times to reduce clutter
    return output_copy