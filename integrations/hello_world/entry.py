from utils.task_registry import register_tasks
from utils.base_runner import BaseRunner, TaskContext


class Runner(BaseRunner):
    name = "hello_world"

    def __init__(self, config):
        config["integration_name"] = self.name
        register_tasks(self.__class__)
        super().__init__(config)

    class StageOne(BaseRunner.StageOne):
        """
        Pre-task execution setup phase.

        This stage allows the integration to inject data (e.g., cloud clients,
        credentials, region info) into the context that will be used by tasks.
        """
        def start(self):
            return self.authenticate()

        def authenticate(self):
            """
            Example setup logic — returns authentication/client info to be used by tasks.
            Replace or extend this method to perform any integration-specific setup.

            Usage in tasks: ctx.base("token")
            """
            return {
                "token": self.config.get("token"),
            }

    class StageTwo(BaseRunner.StageTwo):
        """
        Task execution phase.

        This class acts as a container for dynamically registered tasks via
        @task decorator. Tasks will be attached to this class at runtime.
        """
        pass