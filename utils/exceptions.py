
class TaskNotRun(Exception):
    """Raised when get_result is called and the task has not run yet"""
    pass