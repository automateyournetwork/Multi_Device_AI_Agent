import os
import time
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

import time

def run_linux_command(command: str, device_name: str):
    """
    Execute a Linux command on a specified device (e.g., DESKTOP).
    Uses `device.parse(command)` if a parser exists, otherwise falls back to `device.execute(command)`.
    Ensures `apt install` commands finish before proceeding.
    """
    try:
        logger.info("Loading testbed...")
        testbed = loader.load('testbed.yaml')

        if device_name not in testbed.devices:
            return {"status": "error", "error": f"Device '{device_name}' not found in testbed."}

        device = testbed.devices[device_name]

        if not device.is_connected():
            logger.info(f"Connecting to {device_name} via SSH...")
            device.connect()

        logger.info(f"Executing command on {device_name}: {command}")

        # 🚀 Run installation command with a long timeout
        output = device.execute(command, timeout=300)  # Wait up to 5 minutes if needed

        # If installing a package, wait for confirmation
        if "apt install" in command or "apt-get install" in command:
            package_name = command.split("install -y")[-1].strip()  # Extract package name
            logger.info(f"Package installation detected: {package_name}")

            # 🚀 Loop until package is confirmed installed
            for _ in range(12):  # Check every 10 sec for up to 2 minutes
                check_output = device.execute(f"dpkg -l | grep {package_name}", timeout=10)
                if package_name in check_output:
                    logger.info(f"{package_name} successfully installed.")
                    break
                logger.info(f"Waiting for {package_name} to finish installing...")
                time.sleep(10)
            else:
                logger.warning(f"Timeout waiting for {package_name} installation.")

        logger.info(f"Disconnecting from {device_name}...")
        device.disconnect()

        return {"status": "completed", "device": device_name, "output": output}

    except Exception as e:
        logger.error(f"Error executing command on {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}

@tool("run_linux_command_tool")
def run_linux_command_tool(input_text: str) -> dict:
    """
    Execute a supported Linux command on a specified host.
    Input format: "<device_name>: <command>"
    Example: "DESKTOP: ifconfig -a"
    """
    try:
        device_name, command = input_text.split(":", 1)
        return run_linux_command(command.strip(), device_name.strip())
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}

@tool("execute_linux_command_tool")
def execute_linux_command_tool(input_text: str) -> dict:
    """
    Execute any arbitrary Linux command (including unsupported ones).
    Input format: "<device_name>: <command>"
    Example: "DESKTOP: uname -a"
    """
    try:
        device_name, command = input_text.split(":", 1)
        return run_linux_command(command.strip(), device_name.strip())  # Same function as above
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}

# Define the LLM model
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.6)

# Create tool descriptions
tools = [run_linux_command_tool, execute_linux_command_tool]
tool_descriptions = render_text_description(tools)

# Define the prompt template for Linux commands
template = '''
Assistant is a Linux system administrator AI agent. This is an Ubuntu Linux system so only use Alpine Linux supported commands.

Redirecting output using ">" is allowed. Please do so to create files.

Assistant is designed to assist with Linux system commands, monitoring, and diagnostics. 
It can run system commands like `ifconfig`, `ip route show`, `netstat`, `ps -ef`, and `ls -l` 
on Linux hosts using the provided tools.

When creating text files use echo and the > to redirect the output to the file. Do not use tee use echo > to redirect. 

**INSTRUCTIONS:**
- Assistant can **only** run supported commands: {tool_names}
- If a command is not supported by a parser, use `execute_linux_command_tool` to run it as a raw command.
- To retrieve system information, use `run_linux_command_tool` if a parser exists.
- If unsure, first attempt `run_linux_command_tool`, then fall back to `execute_linux_command_tool`.
- Use echo > to create text files. Do no use tee.
Assistant is a Linux system administrator AI agent. This is an Ubuntu WSL system, so only use Ubuntu-supported commands.

Redirecting output using ">" is allowed. Please do so to create files.

Assistant is designed to assist with Linux system commands, monitoring, diagnostics, and software installation.  
It can run system commands like `ifconfig`, `ip route show`, `netstat`, `ps -ef`, and `ls -l` on Linux hosts using the provided tools.  

When creating text files, use `echo` with `>` to redirect the output to the file. Do **not** use `tee`—always use `echo >` for file creation.

### **INSTRUCTIONS:**
- Assistant can **only** run supported commands: {tool_names}  
- If a command is not supported by a parser, use `execute_linux_command_tool` to run it as a raw command.  
- To retrieve system information, use `run_linux_command_tool` if a parser exists.  
- If unsure, first attempt `run_linux_command_tool`, then fall back to `execute_linux_command_tool`.  
- **If a required package is missing, Assistant should install it using:
    sudo apt install -y <package_name>

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

If the first tool provides a valid command, you MUST immediately run the 'run_linux_command_tool' 
without waiting for another input. If the command is unsupported, use 'execute_linux_command_tool'.  
Follow the flow like this:

### **Example Usage**

#### **If command has a parser (`ifconfig`)**
Thought: Do I need to use a tool? Yes  
Action: run_linux_command_tool  
Action Input: "DESKTOP: ifconfig"  
Observation: [parsed output here]  
Final Answer: [Formatted response]

#### **If command does NOT have a parser (`uname -a`)**
Thought: Do I need to use a tool? Yes  
Action: execute_linux_command_tool  
Action Input: "DESKTOP: uname -a"  
Observation: [raw output from `device.execute`]  
Final Answer: [Formatted response]

#### ** If I am asked to create a file:
Thought: Do I need to use a tool? Yes  
Action: execute_linux_command_tool  
Action Input: "sudo echo 'Hello World' > CreatedbyAI.txt"
Observation: [raw output from `device.execute`]  
Final Answer: [Formatted response]

#### **If software needs to be installed (`sshpass` as an example)**
Thought: Do I need to install software? Yes  
Action: execute_linux_command_tool  
Action Input: "sudo apt install -y sshpass"  
Observation: [installation output]  
Final Answer: "The required package `sshpass` has been installed successfully."

#### **⚠️ IMPORTANT: FILE CREATION RULES**
🚀 **ONLY use `echo >` for file creation. No other method is allowed.**
❌ **Never use:** tee or bash
✅ **Always use:** `echo and the redirect >`

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
