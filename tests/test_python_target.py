from agentgate.contracts import Case, Trace
from agentgate.run.core import LocalScheduler, PythonFunctionTarget


def test_python_function_target_runs_through_local_scheduler():
    case = Case(id="case", name="case", input={"message": "hello"})

    def function(run_id, received_case, version):
        return Trace(run_id=run_id, case_id=received_case.id, spans=(),
                     final_output={"version": version, "message": received_case.input["message"]})

    trace = LocalScheduler().execute(PythonFunctionTarget(function), "run", case, "v1")
    assert trace.final_output == {"version": "v1", "message": "hello"}
