"""In-process background jobs.

Long simulations can be queued and executed on a worker thread. The development
implementation does not depend on Redis or a separate worker process. Request
handlers that pass wait=True run the job on the request thread instead.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.db import get_sessionmaker
from app.models import Project, Scenario, SimulationRun
from app.services.planning import execute_simulation

logger = logging.getLogger("projectverse.jobs")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="projectverse")


def run_queued(run_id: str) -> None:
    session = get_sessionmaker()()
    try:
        run = session.get(SimulationRun, run_id)
        if run is None:
            return
        project = session.get(Project, run.project_id)
        scenario = session.get(Scenario, run.scenario_id) if run.scenario_id else None
        if project is None:
            run.status = "failed"
            run.error_message = "Project no longer exists."
            session.commit()
            return
        execute_simulation(
            session,
            project,
            run_type=run.run_type,
            seed=run.seed,
            iterations=run.iterations,
            scenario=scenario,
            set_baseline=scenario is None and run.run_type == "deterministic",
            existing=run,
        )
        session.commit()
    except ValueError:
        session.commit()
    except Exception:
        logger.exception("Background simulation failed")
        session.rollback()
        run = session.get(SimulationRun, run_id)
        if run is not None and run.status != "completed":
            run.status = "failed"
            run.error_message = "Simulation failed."
            session.commit()
    finally:
        session.close()


def submit_run(run_id: str, wait: bool) -> None:
    if wait:
        run_queued(run_id)
        return
    _executor.submit(run_queued, run_id)
