import os
import json
import difflib
import logging
import textwrap
import textwrap
from pyats.topology import loader
#from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI
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

        # Convert escaped newlines to proper multi-line Python strings
        if "\\n" in config_commands or "\n" in config_commands:
            logger.info("Detected newline characters in the configuration. Converting to multi-line Python string.")
            lines = config_commands.replace("\\n", "\n").strip().split("\n")
            config_commands = "\n".join(lines)

        # Clean and apply configuration
        cleaned_config = textwrap.dedent(config_commands.strip())
        logger.info(f"Applying configuration on {device_name}:\n{cleaned_config}")

        device.configure(cleaned_config)

        logger.info(f"Disconnecting from {device_name}...")
        device.disconnect()

        return {"status": "success", "message": f"Configuration applied successfully on {device_name}."}
    except Exception as e:
        logger.error(f"Error applying configuration: {str(e)}")
        return {"status": "error", "error": str(e)}

# Function to learn the configuration using pyATS
def execute_show_run():
    try:
        # Load the testbed
        logger.info("Loading testbed...")
        testbed = loader.load('testbed.yaml')

        # Access the device from the testbed
        device = testbed.devices['SW2']

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
        device = testbed.devices['SW2']

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

def run_ping_command(command: str, device_name: str):
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

        parsed_output = device.parse(command)
        device.disconnect()

        return {"status": "completed", "device": device_name, "output": parsed_output}

    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool("run_show_command_tool")
def run_show_command_tool(input_text: str) -> dict:
    """
    Execute a 'show' command on a specified device.
    Input format: "<device_name>: <command>"
    Example: "SW2: show ip interface brief"
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
        "SW2: ntp server 192.168.100.100"
        or
        "SW2: interface loopback 100\ndescription AI Created\nip address 10.10.100.100 255.255.255.0\nno shutdown"
    """
    try:
        # Split device name and commands
        device_name, config_commands = input_text.split(":", 1)
        device_name = device_name.strip()
        config_commands = config_commands.strip()

        # Reformat to multi-line Python string
        config_commands = reformat_to_multiline(config_commands)

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

# Define the custom tool for ping
@tool("run_ping_command_tool")
def run_ping_command_tool(input_text: str) -> dict:
    """
    Execute a 'ping' command on a specified device.
    Input format: "<device_name>: <ping_command>"
    Example: "SW2: ping 8.8.8.8"
    """
    try:
        # Split input into device name and ping command
        device_name, command = input_text.split(":", 1)
        device_name = device_name.strip()
        command = command.strip()
        
        return run_ping_command(command, device_name)
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <ping_command>'."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ============================================================
# Define the agent with a custom prompt template
# ============================================================

# Initialize the LLM (you can replace 'gpt-3.5-turbo' with your desired model)
#llm = Ollama(model="command-r7b", base_url="http://ollama:11434")
llm = ChatOpenAI(model_name="gpt-4o", temperature="0.6")

# Create a list of tools
#tools = [run_show_command_tool, check_supported_command_tool, apply_configuration_tool, learn_config_tool, learn_logging_tool]
tools = [run_show_command_tool, apply_configuration_tool, learn_config_tool, learn_logging_tool, run_ping_command_tool]

# Render text descriptions for the tools for inclusion in the prompt
tool_descriptions = render_text_description(tools)

template = '''
Assistant is a large language model trained by OpenAI.

Assistant is designed to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on various topics. As a language model, Assistant can generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide coherent and relevant responses.

Assistant is constantly learning and improving. It can process and understand large amounts of text and use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Assistant can generate its text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on various topics.

NETWORK INSTRUCTIONS:

Assistant is a network assistant with the capability to run tools to gather information, configure the network, and provide accurate answers. You MUST use the provided tools for checking interface statuses, retrieving the running configuration, configuring settings, or finding which commands are supported.

** VERY IMPORTANT ** 
If a configuration has new lines, /n, characters you *MUST* convert this to multi-line Python """ 
If the configuration looks like this: Action Input: "SW2: interface Ethernet0/1\ndescription P2P Link with SW2 Eth0/1"
Convert this to multi-line Python line like this 
""" interface Ethernet0/1
description P2P Link with SW2 Eth0/1
"""

**Important Guidelines:**

** Do NOT use `configure terminal` or `conf t`. Directly provide the configuration commands. The system automatically handles configuration mode. **
** Action Input: should never been "configure terminal" or "conf t" or "config term" it should only and always be configuration or show commands **
** If the input is a configuration command (e.g., `ntp server`, `interface`), use `apply_configuration_tool`.**  
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

** Handling PING Commands **  
If the user asks you to **ping an IP address from a specific device**, convert the request into the correct `ping` command before using the `ping_tool`.  

** Formatting Rules for Ping Requests: **  
- If a source interface is mentioned, use `ping {destination} source {source_interface} repeat {count}`  
- If no source interface is given, use `ping {destination} repeat {count}`  
- Default **repeat count** is **5** unless specified.  
- Ensure the action input follows the format: `"SW2: <destination> [source_interface] [repeat_count]"`  

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

User: *"Can you ping 8.8.8.8 from SW2?"*  
Thought: Do I need to use a tool? Yes  
Action: ping_tool  
Action Input: "SW2: 8.8.8.8 5"  

User: *"Ping 10.10.10.1 from SW2 using GigabitEthernet0/1 for 3 times."*  
Thought: Do I need to use a tool? Yes  
Action: ping_tool  
Action Input: "SW2: 10.10.10.1 GigabitEthernet0/1 3"

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

def reformat_to_multiline(config: str) -> str:
    """
    Convert configuration strings containing '\n' into a proper multi-line Python string.
    """
    if "\\n" in config or "\n" in config:
        # Normalize and format the string
        lines = config.replace("\\n", "\n").strip().split("\n")
        return "\n".join(lines)  # Return as a multi-line string
    return config  # Return unchanged if no newlines are found

def handle_command(command: str, shared_context: dict, device_name: str):
    try:
        # Reformat configuration strings for multi-line inputs
        if not command.strip().lower().startswith("show"):
            logging.info(f"🛠 Reformatting configuration for {device_name}...")

            # Apply transformation to multiline if necessary
            formatted_command = reformat_to_multiline(command)
            input_text = f"{device_name}: {formatted_command}"

            # Pass to the configuration tool
            logging.info(f"🛠 Applying configuration to {device_name}: {formatted_command}")
            response = apply_configuration_tool(input_text)
        else:
            # Handle 'show' commands normally
            logging.info(f"🔍 Running show command on {device_name}: {command}")
            input_text = f"{device_name}: {command.strip()}"
            response = agent_executor.invoke({
                "input": input_text,
                "chat_history": shared_context.get("chat_history", ""),
                "agent_scratchpad": shared_context.get("agent_scratchpad", ""),
            })

        # Log success
        if response.get("status") == "completed":
            shared_context["queried_devices"].add(device_name)
            logging.info(f"✅ Query completed for {device_name}")

        return response

    except Exception as e:
        logging.error(f"❌ Error executing command for {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}