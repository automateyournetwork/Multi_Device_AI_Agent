import os
import json
import logging
from pyats.topology import loader
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.tools import tool, render_text_description
from dotenv import load_dotenv
from genie.libs.parser.utils import get_parser

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of supported Linux commands that `pyATS` can parse
SUPPORTED_LINUX_COMMANDS = [
    "ifconfig",
    "ifconfig {interface}",
    "ip route show table all",
    "ls -l",
    "ls -l {directory}",
    "netstat -rn",
    "ps -ef",
    "ps -ef | grep {grep}",
    "route",
    "route {flag}"
]

def run_linux_command(command: str, device_name: str):
    """
    Execute a supported Linux command on a specified device (e.g., PC1).
    """
    try:
        disallowed_modifiers = ['|', '>', '<']
        for modifier in command.split():
            if modifier in disallowed_modifiers:
                return {"status": "error", "error": f"Command '{command}' contains disallowed modifier '{modifier}'."}

        # Load testbed and target Linux device dynamically
        logger.info("Loading testbed...")
        testbed = loader.load('testbed.yaml')

        if device_name not in testbed.devices:
            return {"status": "error", "error": f"Device '{device_name}' not found in testbed."}

        device = testbed.devices[device_name]

        # Establish connection if not already connected
        if not device.is_connected():
            logger.info(f"Connecting to {device_name} via SSH...")
            device.connect()

        # Ensure command is supported
        parser = get_parser(command, device)
        if parser is None:
            return {"status": "error", "error": f"No parser available for command: {command}"}

        logger.info(f"Executing and parsing command on {device_name}: {command}")
        parsed_output = device.parse(command)

        # Disconnect after execution
        logger.info(f"Disconnecting from {device_name}...")
        device.disconnect()

        return {"status": "completed", "device": device_name, "output": parsed_output}

    except Exception as e:
        logger.error(f"Error executing command on {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}

@tool("run_linux_command_tool")
def run_linux_command_tool(input_text: str) -> dict:
    """
    Execute a supported Linux command on a specified host.
    Input format: "<device_name>: <command>"
    Example: "PC1: ifconfig -a"
    """
    try:
        device_name, command = input_text.split(":", 1)
        device_name = device_name.strip()
        command = command.strip()
        
        return run_linux_command(command, device_name)
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Define the LLM model
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.6)

# Create tool descriptions
tools = [run_linux_command_tool]
tool_descriptions = render_text_description(tools)

# Define the prompt template for Linux commands
template = '''
Assistant is a Linux system administrator AI agent.

Assistant is designed to assist with Linux system commands, monitoring, and diagnostics. It can run system commands like `ifconfig`, `ip route show`, `netstat`, `ps -ef`, and `ls -l` on Linux hosts using the provided tools.

**INSTRUCTIONS:**
- Assistant can **only** run supported commands: {tool_names}
- If a command is not supported, inform the user.
- To retrieve system information, use `run_linux_command_tool`.

**TOOLS:**  
{tools}

**Available Tool Names (use exactly as written):**  
{tool_names}

To use a tool, follow this format:

**FORMAT:**
Thought: Do I need to use a tool? Yes  
Action: the action to take, should be one of [{tool_names}]  
Action Input: the input to the action  
Observation: the result of the action
Final Answer: [Answer to the User]  

If the first tool provides a valid command, you MUST immediately run the 'run_show_command_tool' without waiting for another input. Follow the flow like this:

Example:

**FORMAT:**
Thought: Do I need to use a tool? Yes  
Action: run_linux_command_tool  
Action Input: "<device_name>: <command>"  
Observation: [parsed output here]  

If a response is ready, return:
Thought: Do I need to use a tool? No  
Final Answer: [your response here]

Begin!

{chat_history}

New input: {input}

{agent_scratchpad}
'''

# Create the agent
input_variables = ["input", "agent_scratchpad", "chat_history"]
prompt_template = PromptTemplate(
    template=template,
    input_variables=input_variables,
    partial_variables={
        "tool_names": ", ".join([t.name for t in tools])
    }
)

agent = create_react_agent(llm, tools, prompt_template)

# Initialize the agent executor
agent_executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True, verbose=True, max_iterations=50)

def handle_command(command: str, device_name: str):
    """
    Handle and execute Linux system commands.
    """
    try:
        logging.info(f"Executing command on {device_name}: {command}")
        input_text = f"{device_name}: {command.strip()}"
        response = agent_executor.invoke({
            "input": input_text,
            "chat_history": "",
            "agent_scratchpad": "",
        })
        return response
    except Exception as e:
        logging.error(f"Error executing command on {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}
