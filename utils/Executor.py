from utils.schemas import Plan, PlannerTask
from MCP.client import MCPClient


class Executor:
    """Executor Class.

    Methods:


    Attributes:


    """

    def __init__(self, mcp_client: MCPClient):
        """
        Initialize the orchestrator
        """
        self.mcp_client = mcp_client
        self.tool_call_history: list = []
        self.previous_task_results: list = [{"first task, no previous task yet"}]

    def print_task(self, task: PlannerTask) -> None:
        """Print the given task generated by the planner agent

        Args:
            task: The task to print.
            previous_task_results: The results of the previous task.

        Returns:
            None
        """
        print(f"""
              Executing task: \n
              Task ID: {task.id} \n
              Task description: {task.description} \n
              Task Thought: {task.thought} \n
              Tool calls: {task.tool_calls} \n
              Task status: {task.status} \n
              Previous Task Results: {self.previous_task_results}
        """)

    def print_plan(self, plan: Plan) -> None:
        """Print the given plan generated by the planner agent

        Args:
            plan: The plan to print.

        Returns:
            None
        """
        print(f"""
              Plan to execute is: \n
              Plan ID: {plan.original_query}
              Plan Description: {plan.description}
         """)

    async def call_tools(self, tool_calls: list[dict]) -> list[dict]:
        """Receives a list of tool calls and calls the tools

        Args:
            tool_calls: Either a list of tool call dicts or a string error message

        Returns:
            list[dict]: The results of the tool calls or error information
        """
        # If we received an error message instead of tool calls
        if isinstance(tool_calls, str):
            return [{"error": True, "message": tool_calls}]

        # # Ensure tool_calls is a list
        if not isinstance(tool_calls, list):
            return [
                {
                    "error": True,
                    "message": f"Expected list of tool calls, got {type(tool_calls).__name__}",
                }
            ]
        results = []  # Tool call results
        print("CALLING_TOOLS ... ")
        for tool in tool_calls:  # For each tool
            try:  # Try to call the tool
                if not isinstance(tool, dict):  # If tool is not a dict return error
                    results.append(
                        {
                            "error": True,
                            "message": f"Expected dict, got {type(tool).__name__}",
                        }
                    )
                    continue
                # Extract tool name and arguments
                name = tool["name"]
                arguments = tool["arguments"]
                print(f"CALLING TOOL: {name}")
                if not name:
                    results.append(
                        {"error": True, "message": "Tool call missing 'name' field"}
                    )
                    continue

                # Call the tool through MCP client
                result = await self.mcp_client.call_tool(name, arguments)
                # append tool call reults. Includes name, arguments, and result
                results.append({"result": result})
                self.tool_call_history.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "result": result,
                        "error": False,
                    }
                )

            # Handle exceptions
            except Exception as e:
                print("AT EXCEPTION")
                results.append(
                    {
                        "error": True,
                        "name": name if "name" in locals() else "unknown",
                        "message": f"Error calling tool: {str(e)}",
                    }
                )
        print(f"TOOL CALL RESULTS: {results}")
        return results

    async def execute_task(self, task: PlannerTask) -> list[dict]:
        """Execute the given task generated by the planner agent

        Args:
            task: The task to execute.

        Returns:
            A list of results

        """

        # print current task
        self.print_task(task)
        tool_calls = []  # list to hold tool_calls in current task
        for i in range(len(task.tool_calls)):  # for every tool call in the task
            tool_call = task.tool_calls[i]  # select the tool call
            tools = self.extract_tools(
                tool_call
            )  # extract the tool into {name: tool_name, arguments: {...}
            tool_calls.append(tools)  # add tool to tool_Calls list

        print(f"TOOL_CALLS: {tool_calls}")
        tool_call_results = await self.call_tools(
            tool_calls
        )  # call the tools, should return [{'result': result} ...]
        results = [
            result["result"] for result in tool_call_results if "result" in result
        ]  # get the results only

        return results
        # return ''

    def extract_tools(self, tool_call):
        """
        Extracts tool name and its arguments from a tool_call object,
        applying special rules for known tools like review_tool, writer_tool, and save_txt.
        """
        name = tool_call.name.split(".")[-1]

        tool = {"name": name, "arguments": {}}

        keys = tool_call.arguments.keys
        values = tool_call.arguments.values

        if len(keys) != len(values):
            raise ValueError(
                f"Tool call argument mismatch: keys={keys}, values={values}"
            )

        for key, value in zip(keys, values):
            # --- Tool-specific overrides ---
            if name in ("review_tool", "assemble_content") and key == "content":
                tool["arguments"]["content"] = str(self.previous_task_results)

            elif name == "writer_tool":
                if key == "content":
                    tool["arguments"]["context"] = str(self.tool_call_history)
                elif key == "query":
                    tool["arguments"]["query"] = value
                else:
                    tool["arguments"][key] = value

            elif name == "save_txt":
                if key == "text":
                    tool["arguments"]["text"] = str(self.previous_task_results)
                elif key == "filename":
                    tool["arguments"]["filename"] = value
                else:
                    tool["arguments"][key] = value

            # --- Default fallback ---
            else:
                tool["arguments"][key] = value

        return tool

    async def execute_plan(self, plan: Plan) -> list:
        """Execute the given plan generated by the planner agent

        Args:
            plan: The plan to execute.

        Returns:
            A list of results
        """
        self.print_plan(plan)  # print the plan
        results = [
            {
                "task": "No task yet",
                "results": "No task results yet",
            }
        ]  # list to hold results of each task execution.
        for i in range(len(plan.tasks)):  # iterate through tasks
            task: PlannerTask = plan.tasks[i]  # select the task
            res = await self.execute_task(task)  # execute task
            # append task execution results to list
            self.previous_task_results.append(
                {
                    "task_id": task.id,
                    "task": task.description,
                    "results": res,
                }
            )

        return results
