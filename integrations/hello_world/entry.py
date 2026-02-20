from utils.base_runner import BaseRunner, TaskContext


class Runner(BaseRunner):

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

        Tasks are dynamically registered to this class at runtime via the @task
        decorator — do not add task methods manually here.

        You can override this class if you need to perform setup before tasks
        run, but this is rarely needed. In most cases, leave this as-is and
        put all setup logic in StageOne.
        """
        pass