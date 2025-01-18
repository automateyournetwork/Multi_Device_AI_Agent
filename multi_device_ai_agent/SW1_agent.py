import os
import json
import difflib
import logging
from pyats.topology import loader
#from langchain_community.llms import Ollama
from langchain.chat_models import ChatOpenAI
from langchain_core.tools import tool, render_text_description
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from genie.libs.parser.utils import get_parser
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_show_command(command: str, device_name: str):
    try:
        disallowed_modifiers = ['|', 'include', 'exclude', 'begin', 'redirect', '>', '<']
        for modifier in command.split():
            if modifier in disallowed_modifiers:
                return {"status": "error", "error": f"Command '{command}' contains disallowed modifier '{modifier}'."}

        # Load testbed and target device dynamically
        testbed = loader.load('testbed.yaml')
        device = testbed.devices.get(device_name)

        if not device:
            return {"status": "error", "error": f"Device '{device_name}' not found in testbed."}

        if not device.is_connected():
            device.connect()

        parser = get_parser(command, device)
        if parser is None:
            return {"status": "error", "error": f"No parser available for command: {command}"}

        parsed_output = device.parse(command)
        device.disconnect()

        return {"status": "completed", "device": device_name, "output": parsed_output}

    except Exception as e:
        return {"status": "error", "error": str(e)}

# Function to load supported commands from a JSON file
def load_supported_commands():
    file_path = 'commands.json'  # Ensure the file is named correctly

    # Check if the file exists
    if not os.path.exists(file_path):
        return {"error": f"Supported commands file '{file_path}' not found."}

    try:
        # Load the JSON file with the list of commands
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Extract the command strings into a list
        command_list = [entry['command'] for entry in data]
        return command_list
    except Exception as e:
        return {"error": f"Error loading supported commands: {str(e)}"}

# Function to check if a command is supported with fuzzy matching
def check_command_support(command: str) -> dict:
    command_list = load_supported_commands()

    if "error" in command_list:
        return command_list

    # Find the closest matches to the input command using difflib
    close_matches = difflib.get_close_matches(command, command_list, n=1, cutoff=0.6)

    if close_matches:
        closest_command = close_matches[0]
        return {"status": "supported", "closest_command": closest_command}
    else:
        return {"status": "unsupported", "message": f"The command '{command}' is not supported. Please check the available commands."}

def process_agent_response(response):
    if response.get("status") == "supported" and "next_tool" in response.get("action", {}):
        next_tool = response["action"]["next_tool"]
        command_input = response["action"]["input"]

        # Automatically invoke the next tool (run_show_command_tool)
        return agent_executor.invoke({
            "input": command_input,
            "chat_history": "",  # Removed streamlit dependency
            "agent_scratchpad": "",
            "tool": next_tool
        })
    else:
        return response

def apply_device_configuration(device_name: str, config_commands: str):
    try:
        logger.info(f"Loading testbed...")
        testbed = loader.load('testbed.yaml')

        device = testbed.devices.get(device_name)
        if not device:
            return {"status": "error", "error": f"Device '{device_name}' not found in testbed."}

        logger.info(f"Connecting to device {device_name}...")
        if not device.is_connected():
            device.connect()

        # Filter out 'configure terminal' and 'end'
        filtered_commands = "\n".join([
            cmd for cmd in config_commands.splitlines()
            if "configure terminal" not in cmd.lower() and "end" not in cmd.lower()
        ])

        logger.info(f"Applying configuration on {device_name}:\n{filtered_commands}")
        device.configure(filtered_commands)

        logger.info(f"Disconnecting from {device_name}...")
        device.disconnect()

        return {"status": "success", "message": f"Configuration applied successfully on {device_name}."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Function to learn the configuration using pyATS
def execute_show_run():
    try:
        # Load the testbed
        logger.info("Loading testbed...")
        testbed = loader.load('testbed.yaml')

        # Access the device from the testbed
        device = testbed.devices['SW1']

        # Connect to the device
        logger.info("Connecting to device...")
        device.connect()

        # Use the pyATS learn function to gather the configuration
        logger.info("Learning configuration...")
        learned_config = device.execute('show run brief')

        # Close the connection
        logger.info("Disconnecting from device...")
        device.disconnect()

        # Return the learned configuration as JSON
        return learned_config
    except Exception as e:
        # Handle exceptions and provide error information
        return {"error": str(e)}

# Function to learn the configuration using pyATS
def execute_show_logging():
    try:
        # Load the testbed
        logger.info("Loading testbed...")
        testbed = loader.load('testbed.yaml')

        # Access the device from the testbed
        device = testbed.devices['SW1']

        # Connect to the device
        logger.info("Connecting to device...")
        device.connect()

        # Use the pyATS learn function to gather the configuration
        logger.info("Learning configuration...")
        learned_logs = device.execute('show logging last 250')

        # Close the connection
        logger.info("Disconnecting from device...")
        device.disconnect()

        # Return the learned configuration as JSON
        return learned_logs
    except Exception as e:
        # Handle exceptions and provide error information
        return {"error": str(e)}

@tool("run_show_command_tool")
def run_show_command_tool(input_text: str) -> dict:
    """
    Execute a 'show' command on a specified device.
    Input format: "<device_name>: <command>"
    Example: "R1: show ip interface brief"
    """
    try:
        # Split input into device name and command
        device_name, command = input_text.split(":", 1)
        device_name = device_name.strip()
        command = command.strip()
        
        return run_show_command(command, device_name)
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool
def check_supported_command_tool(input_text: str) -> dict:
    """
    Check if a command is supported. Input format: "<device_name>: <command>"
    """
    try:
        device_name, command = input_text.split(":", 1)
        command = command.strip()
        
        result = check_command_support(command)
        if result.get('status') == 'supported':
            closest_command = result['closest_command']
            return {
                "status": "supported",
                "message": f"The closest supported command is '{closest_command}'",
                "action": {
                    "next_tool": "run_show_command_tool",
                    "input": f"{device_name}: {closest_command}"  # Pass as single input
                }
            }
        return result
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}

# Define the custom tool for configuration changes
@tool
def apply_configuration_tool(input_text: str) -> dict:
    """
    Apply configuration commands on the specified device.

    Input format: "<device_name>: <configuration_commands>"
    Example:
        "R1: ntp server 192.168.100.100"
        or
        "SW2: interface loopback 100\n description AI Created\n ip address 10.10.100.100 255.255.255.0\n no shutdown"
    """
    try:
        # Split device name and commands
        device_name, config_commands = input_text.split(":", 1)
        device_name = device_name.strip()
        config_commands = config_commands.strip()

        logging.info(f"🛠 Applying configuration on {device_name}: {config_commands}")
        return apply_device_configuration(device_name, config_commands)

    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <configuration_commands>'."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Define the custom tool for learning the configuration
@tool
def learn_config_tool(dummy_input: str = "") -> dict:
    """Excute show run brief on the router using pyATS to return the running-configuration."""
    return execute_show_run()

# Define the custom tool for learning the configuration
@tool
def learn_logging_tool(dummy_input: str = "") -> dict:
    """Execute show logging on the router using pyATS and return it as raw text."""
    return execute_show_logging()

# ============================================================
# Define the agent with a custom prompt template
# ============================================================

# Initialize the LLM (you can replace 'gpt-3.5-turbo' with your desired model)
#llm = Ollama(model="command-r7b", temperature=0.3, base_url="http://ollama:11434")
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)

# Create a list of tools
tools = [run_show_command_tool, check_supported_command_tool, apply_configuration_tool, learn_config_tool, learn_logging_tool]

# Render text descriptions for the tools for inclusion in the prompt
tool_descriptions = render_text_description(tools)

template = '''
Assistant is a large language model trained by OpenAI.

Assistant is designed to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on various topics. As a language model, Assistant can generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide coherent and relevant responses.

Assistant is constantly learning and improving. It can process and understand large amounts of text and use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Assistant can generate its text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on various topics.

NETWORK INSTRUCTIONS:

Assistant is a network assistant with the capability to run tools to gather information, configure the network, and provide accurate answers. You MUST use the provided tools for checking interface statuses, retrieving the running configuration, configuring settings, or finding which commands are supported.

**Important Guidelines:**

** Do NOT use `configure terminal` or `conf t`. Directly provide the configuration commands. The system automatically handles configuration mode. **
** Action Input: should never been "configure terminal" or "conf t" or "config term" it should only and always be configuration or show commands **
** Do NOT check configuration commands with `check_supported_command_tool`.**  
** If the input is a configuration command (e.g., `ntp server`, `interface`), use `apply_configuration_tool`.**  
** Only use `check_supported_command_tool` for 'show' or informational commands.**
** If you are certain of the command for retrieving information, use the 'run_show_command_tool' to execute it.**
** If you need access to the full running configuration, use the 'learn_config_tool' to retrieve it.**
** If you are unsure of the command or if there is ambiguity, use the 'check_supported_command_tool' to verify the command or get a list of available commands.**
** If the 'check_supported_command_tool' finds a valid command, automatically use 'run_show_command_tool' to run that command.**
** For configuration changes, use the 'apply_configuration_tool' with the necessary configuration string (single or multi-line).**
** Do NOT use any command modifiers such as pipes (`|`), `include`, `exclude`, `begin`, `redirect`, or any other modifiers.**
** If the command is not recognized, always use the 'check_supported_command_tool' to clarify the command before proceeding.**

**Using the Tools:**

- If you are confident about the command to retrieve data, use the 'run_show_command_tool'.
- If you need access to the full running configuration, use 'learn_config_tool'.
- If there is any doubt or ambiguity, always check the command first with the 'check_supported_command_tool'.
- If you need to apply a configuration change, use 'apply_configuration_tool' with the appropriate configuration commands.

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

Thought: Do I need to use a tool? Yes  
Action: check_supported_command_tool  
Action Input: "show ip access-lists"  
Observation: "The closest supported command is 'show ip access-list'."

Thought: Do I need to use a tool? Yes  
Action: run_show_command_tool  
Action Input: "show ip access-list"  
Observation: [parsed output here]

If you need access to the full running configuration:

Example:

Thought: Do I need to use a tool? Yes  
Action: learn_config_tool  
Action Input: (No input required)  
Observation: [configuration here]

If you need to apply a configuration:

Example:

Thought: Do I need to use a tool? Yes  
Action: apply_configuration_tool  
Action Input: """  
interface loopback 100  
description AI Created  
ip address 10.10.100.100 255.255.255.0  
no shutdown  
"""  
Observation: "Configuration applied successfully."

Example:

Thought: Do I need to use a tool? Yes  
Action: apply_configuration_tool  
Action Input: "ntp server 192.168.100.100"
Observation: "Configuration applied successfully."

** Important ** for configuration management do NOT enter configure terminal mode the agent code will handle that with pyATS

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

Thought: Do I need to use a tool? No  
Final Answer: [your response here]

Correct Formatting is Essential: Ensure that every response follows the format strictly to avoid errors.

TOOLS:

Assistant has access to the following tools:

- check_supported_command_tool: Finds and returns the closest supported commands.
- run_show_command_tool: Executes a supported 'show' command on the network device and returns the parsed output.
- apply_configuration_tool: Applies the provided configuration commands on the network device.
- learn_config_tool: Learns the running configuration from the network device and returns it as JSON.

Begin!

Previous conversation history:

{chat_history}

New input: {input}

{agent_scratchpad}
'''

# Define the input variables separately
input_variables = ["input", "agent_scratchpad", "chat_history"]

# Create the PromptTemplate using the complete template and input variables
prompt_template = PromptTemplate(
    template=template,
    input_variables=input_variables,
    partial_variables={
        "tools": tool_descriptions,
        "tool_names": ", ".join([t.name for t in tools])
    }
)

# Create the ReAct agent using the Ollama LLM, tools, and custom prompt template
agent = create_react_agent(llm, tools, prompt_template)

# ============================================================
# Streamlit App
# ============================================================

# Initialize the agent executor
agent_executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True, verbose=True, max_iterations=50)

def handle_command(command: str, shared_context: dict, device_name: str):
    try:
        input_text = f"{device_name}: {command}"

        # If the command does NOT start with 'show', treat it as a configuration command
        if not command.strip().lower().startswith("show"):
            logging.info(f"🛠 Applying configuration on {device_name}: {command}")
            response = apply_configuration_tool(command)
        else:
            logging.info(f"🔍 Running show command on {device_name}: {command}")
            response = agent_executor.invoke({
                "input": input_text,
                "chat_history": shared_context.get("chat_history", ""),
                "agent_scratchpad": shared_context.get("agent_scratchpad", "")
            })

        if response.get("status") == "completed":
            shared_context["queried_devices"].add(device_name)
            logging.info(f"✅ {device_name} query completed.")

        return response

    except Exception as e:
        logging.error(f"❌ Error executing command for {device_name}: {str(e)}")
        return {"status": "error", "error": f"Failed to execute command on {device_name}: {str(e)}"}
