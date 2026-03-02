"""
Agent client utility for the Orcha UI.
Provides functions to communicate with Orcha Agents running
in workspace/task-runner environments.
"""
import requests

from orcha.utils.log import LogManager

_agent_log = LogManager('agent_client')

# Cache for agent info to avoid repeated calls
_agent_cache: dict[str, dict] = {}
_TIMEOUT = 10  # seconds


def get_agent_info(agent_url: str) -> dict | None:
    """
    Get agent info from a single agent URL.
    Returns None if the agent is unreachable.
    """
    try:
        response = requests.get(f'{agent_url}/agent/info', timeout=_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            _agent_cache[agent_url] = data
            return data
    except Exception as e:
        _agent_log.add_entry(
            actor='agent_client', category='error',
            text=f'Failed to connect to agent: {agent_url}',
            json={'error': str(e)}
        )
    return None


def get_all_agents(agent_urls: list[str]) -> list[dict]:
    """
    Get info from all configured agents. Returns list of agent info dicts.
    """
    agents = []
    for url in agent_urls:
        info = get_agent_info(url)
        if info:
            info['agent_url'] = url
            agents.append(info)
    return agents


def get_modules(agent_url: str) -> dict | None:
    """Get all modules from an agent."""
    try:
        response = requests.get(f'{agent_url}/agent/modules', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        _agent_log.add_entry(
            actor='agent_client', category='error',
            text=f'Failed to get modules from agent: {agent_url}',
            json={'error': str(e)}
        )
    return None


def get_tasks(agent_url: str) -> dict | None:
    """Get all tasks from an agent."""
    try:
        response = requests.get(f'{agent_url}/agent/tasks', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        _agent_log.add_entry(
            actor='agent_client', category='error',
            text=f'Failed to get tasks from agent: {agent_url}',
            json={'error': str(e)}
        )
    return None


def get_task_runners(agent_url: str) -> dict | None:
    """Get task runner info from an agent."""
    try:
        response = requests.get(f'{agent_url}/agent/task_runners', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None


def get_secret_names(agent_url: str) -> list[str]:
    """Get secret names from an agent (names only, not values)."""
    try:
        response = requests.get(f'{agent_url}/agent/secrets', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json().get('secret_names', [])
    except Exception as e:
        pass
    return []


def get_module_types(agent_url: str) -> dict | None:
    """Get available module types with their constructor signatures."""
    try:
        response = requests.get(f'{agent_url}/agent/module_types', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None


def get_pickles(agent_url: str) -> list[dict]:
    """Get all pickled objects from an agent."""
    try:
        response = requests.get(f'{agent_url}/agent/pickles', timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json().get('pickles', [])
    except Exception as e:
        pass
    return []


def deploy_pickle(
        agent_url: str,
        name: str,
        pickle_type: str,
        source_code: str,
        description: str = '',
        module_idk: str | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> dict:
    """Deploy a pickled object to an agent."""
    try:
        response = requests.post(
            f'{agent_url}/agent/pickle/deploy',
            json={
                'name': name,
                'pickle_type': pickle_type,
                'source_code': source_code,
                'description': description,
                'module_idk': module_idk,
                'metadata': metadata,
                'created_by': created_by,
            },
            timeout=30,
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


def deploy_pickle_task(
        agent_url: str,
        task_idk: str,
        name: str,
        description: str,
        source_code: str,
        schedule_sets: list[dict],
        thread_group: str = 'pickle_tasks',
        task_tags: list[str] | None = None,
        task_metadata: dict | None = None,
        created_by: str | None = None,
    ) -> dict:
    """Deploy a pickled task to an agent."""
    try:
        response = requests.post(
            f'{agent_url}/agent/pickle/deploy_task',
            json={
                'task_idk': task_idk,
                'name': name,
                'description': description,
                'source_code': source_code,
                'schedule_sets': schedule_sets,
                'thread_group': thread_group,
                'task_tags': task_tags or ['pickle'],
                'task_metadata': task_metadata or {},
                'created_by': created_by,
            },
            timeout=30,
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


def delete_pickle(agent_url: str, pickle_idk: str) -> dict:
    """Delete a pickle from an agent."""
    try:
        response = requests.delete(
            f'{agent_url}/agent/pickle/{pickle_idk}',
            timeout=_TIMEOUT,
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


def check_code(agent_url: str, source_code: str, pickle_type: str = 'task') -> dict:
    """Ask an agent to compile/syntax-check code without running it."""
    try:
        response = requests.post(
            f'{agent_url}/agent/check_code',
            json={
                'source_code': source_code,
                'pickle_type': pickle_type,
            },
            timeout=30,
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


def test_code(agent_url: str, source_code: str, pickle_type: str = 'task') -> dict:
    """Ask an agent to compile AND execute code (task_function called with None args)."""
    try:
        response = requests.post(
            f'{agent_url}/agent/test_code',
            json={
                'source_code': source_code,
                'pickle_type': pickle_type,
            },
            timeout=60,
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}
