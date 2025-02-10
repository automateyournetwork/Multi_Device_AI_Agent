import os
import json
import logging
import requests
import textwrap
from langchain.tools import Tool  # Import Tool instead of using @tool decorator
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.tools import tool, render_text_description
import urllib3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
os.environ['NETBOX_URL']  = os.getenv("NETBOX_BASE_URL")
os.environ['NETBOX_TOKEN'] = os.getenv("NETBOX_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global variables for lazy initialization
llm = None
agent_executor = None

# NetBoxController for CRUD Operations
class NetBoxController:
    def __init__(self, netbox_url, api_token):
        self.netbox = netbox_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f"Token {self.api_token}",
        }

    def get_api(self, api_url: str, params: dict = None):
        """
        Perform a GET request to the specified NetBox API endpoint.
        """
        full_url = f"{self.netbox}/{api_url.lstrip('/')}"
        logging.info(f"GET Request to URL: {full_url}")
        logging.info(f"Headers: {self.headers}")
        logging.info(f"Params: {params}")
        
        try:
            response = requests.get(full_url, headers=self.headers, params=params, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"GET request failed: {e}")
            return {"error": f"Request failed: {e}"}

    def post_api(self, api_url: str, payload: dict):
        full_url = f"{self.netbox}{api_url}"
        logging.info(f"POST Request to URL: {full_url}")
        logging.info(f"Headers: {self.headers}")
        logging.info(f"Payload: {json.dumps(payload)}")
    
        try:
            response = requests.post(
                full_url,
                headers=self.headers,
                json=payload,
                verify=False
            )
            logging.info(f"Response Status Code: {response.status_code}")
            logging.info(f"Response Content: {response.text}")
    
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"POST request failed: {e}")
            return {"error": f"Request failed: {e}"}

    def delete_api(self, api_url: str):
        full_url = f"{self.netbox}{api_url}"
        logging.info(f"🗑️ DELETE Request to URL: {full_url}")
        logging.info(f"Headers: {self.headers}")

        try:
            response = requests.delete(
                full_url,
                headers=self.headers,
                verify=False
            )

            logging.info(f"📡 Response Status Code: {response.status_code}")
            logging.info(f"📦 Response Content: {response.text}")

            if response.status_code == 204:
                logging.info(f"✅ Deletion successful for {full_url}")
                return {"status": "success", "message": "Deletion successful."}
            else:
                logging.warning(f"⚠️ Deletion failed. Status code: {response.status_code}")
                return {"error": f"Failed to delete. Status code: {response.status_code}"}

        except requests.exceptions.RequestException as e:
            logging.error(f"❌ DELETE request failed: {e}")
            return {"error": f"Request failed: {e}"}
        
# Function to load supported URLs with their names from a JSON file
def load_urls(file_path='netbox_apis.json'):
    if not os.path.exists(file_path):
        return {"error": f"URLs file '{file_path}' not found."}
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return [(entry['URL'], entry.get('Name', '')) for entry in data]
    except Exception as e:
        return {"error": f"Error loading URLs: {str(e)}"}

get_netbox_data_tool = Tool(
    name="get_netbox_data_tool",
    description="Fetch data from NetBox using the correct API URL.",
    func=lambda input_data: get_data_directly(input_data.get("api_url"))  # No 'payload' needed for GET
)

def get_data_directly(api_url: str):
    if not api_url:
        return {"error": "Missing required field `api_url` in input data."}

    try:
        # Initialize the NetBoxController
        netbox_controller = NetBoxController(
            netbox_url=os.getenv("NETBOX_URL"),
            api_token=os.getenv("NETBOX_TOKEN")
        )

        # Call the API directly
        logging.info(f"Fetching data directly from API: {api_url}")
        data = netbox_controller.get_api(api_url)

        # Detect and format configurations with newlines
        if isinstance(data, dict) and "config" in data:
            config = data["config"]
            if "\\n" in config or "\n" in config:
                logging.info("Detected configuration with newlines. Formatting as multi-line string.")
                lines = config.replace("\\n", "\n").strip().split("\n")
                data["config"] = f'"""\n{textwrap.dedent("\n".join(lines))}\n"""'

        return {"status": "success", "message": "Data fetched successfully.", "data": data}

    except Exception as e:
        logging.error(f"Error while fetching data from API: {str(e)}")
        return {"error": f"GET request failed: {str(e)}"}

# ✅ Improved Create NetBox Data Tool
create_netbox_data_tool = Tool(
    name="create_netbox_data_tool",
    description="Create new data in NetBox. Requires 'api_url' and 'payload'.",
    func=lambda input_data: create_data_handler(input_data)
)

def create_data_handler(input_data):
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON input. Expected a JSON object."}

    api_url = input_data.get("api_url")
    payload = input_data.get("payload")

    if not api_url or not isinstance(payload, dict):
        return {"error": "Both 'api_url' and a valid 'payload' dictionary are required."}

    try:
        netbox_controller = NetBoxController(
            netbox_url=os.getenv("NETBOX_URL"),
            api_token=os.getenv("NETBOX_TOKEN")
        )
        response = netbox_controller.post_api(api_url, payload)
        return {
            "status": "success",
            "message": f"Successfully created resource at {api_url}.",
            "response": response
        }

    except requests.exceptions.HTTPError as http_err:
        return {"error": f"HTTP error occurred: {http_err}"}
    except Exception as e:
        return {"error": f"POST request failed: {str(e)}"}

def delete_data_handler(input_data):
    logging.info("🚀 delete_data_handler was called.")
    logging.info(f"📝 Input Data: {json.dumps(input_data, indent=2)}")

    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError:
            logging.error("❌ Invalid JSON input provided to delete_data_handler.")
            return {"error": "Invalid JSON input. Expected a JSON object."}

    api_url = input_data.get("api_url")
    payload = input_data.get("payload", {})
    name = payload.get("name")

    if not api_url or not name:
        logging.error("❌ Missing 'api_url' or 'name' in payload.")
        return {"error": "Both 'api_url' and 'payload' with 'name' are required."}

    try:
        logging.info(f"🔍 Looking up provider '{name}' at {api_url}")

        netbox_controller = NetBoxController(
            netbox_url=os.getenv("NETBOX_URL"),
            api_token=os.getenv("NETBOX_TOKEN")
        )

        # Lookup entity by name to get its ID
        lookup_response = netbox_controller.get_api(api_url, params={'name': name})
        logging.info(f"📦 Lookup response: {json.dumps(lookup_response, indent=2)}")

        if lookup_response.get('count', 0) == 0:
            logging.warning(f"⚠️ No provider found with the name '{name}'.")
            return {"error": f"No resource found at '{api_url}' with name '{name}'."}

        entity_id = lookup_response['results'][0]['id']
        delete_url = f"{api_url.rstrip('/')}/{entity_id}/"

        logging.info(f"🗑️ Preparing to DELETE at {delete_url}")

        # Perform the deletion
        delete_response = netbox_controller.delete_api(delete_url)
        logging.info(f"📝 DELETE response: {delete_response}")

        if delete_response.get("status") == "success":
            return {
                "status": "success",
                "message": f"Successfully deleted '{name}' at {api_url}."
            }
        else:
            return {"error": delete_response.get("error", "Unknown error during deletion.")}

    except Exception as e:
        logging.error(f"❌ Error in delete_data_handler: {e}")
        return {"error": f"Error deleting data: {str(e)}"}
    
delete_netbox_data_tool = Tool(
    name="delete_netbox_data_tool",
    description="Delete data in NetBox. Requires 'api_url' and 'payload' with 'name'.",
    func=delete_data_handler
)

def process_agent_response(response):
    if not isinstance(response, dict):
        logging.error(f"Unexpected response format: {response}")
        return {"error": "Unexpected response format. Please check the input."}

    if response.get("status") == "success":
        return response

    if response.get("status") == "supported" and "next_tool" in response.get("action", {}):
        next_tool = response["action"]["next_tool"]
        tool_input = response["action"]["input"]

        return agent_executor.invoke({
            "input": tool_input,
            "chat_history": "",
            "agent_scratchpad": "",
            "tool": next_tool
        })

    return response

# Initialize the LLM (you can replace 'gpt-3.5-turbo' with your desired model)
#llm = Ollama(model="command-r7b", base_url="http://ollama:11434")
llm = ChatOpenAI(model_name="gpt-4o", temperature="0.6")
# ✅ Define the tools
tools = [
    Tool(name="get_netbox_data_tool", func=get_data_directly, description="Fetch data from NetBox using a valid API URL."),
    Tool(name="create_netbox_data_tool", func=create_data_handler, description="Create new data in NetBox with an API URL and payload."),
    Tool(name="delete_netbox_data_tool", func=delete_data_handler, description="Delete data in NetBox with an API URL and payload."),
]
# Extract tool names and descriptions
tool_names = ", ".join([tool.name for tool in tools])
tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])
# ✅ Updated PromptTemplate
prompt_template = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tool_names", "tools"],
    template='''
    You are a network assistant managing NetBox data using CRUD operations.

    Always use the API URL provided in the Action Input without modifying it or validating it.

    **Important Formatting Guidelines for Configuration Outputs:**
    Never add %22%0A or anything else appending to the NetBox URLs 
    
    **TOOLS:**  
    {tools}

    **Available Tool Names (use exactly as written):**  
    {tool_names}

    **FORMAT:**  
    Thought: [Your reasoning]  
    Action: [Tool Name]  
    Action Input: {{ "api_url": "YOUR_API_URL" }}  
    Observation: [Result]  
    Final Answer: [Answer to the User]  

    **Examples:**
    - To get interfaces from a device called R1:  
      Thought: I need to get the interfaces from R1.  
      Action: get_netbox_data_tool  
      Action Input: {{ "api_url": "/api/dcim/interfaces/?device=R1" }}
         
    - To fetch all circuits:  
      Thought: I need to retrieve all circuits from NetBox.  
      Action: get_netbox_data_tool  
      Action Input: {{ "api_url": "/api/circuits/" }}
    
    - To create a provider called "Bell Canada":  
      Thought: I need to create a provider named 'Bell Canada' with the slug 'bell'.  
      Action: create_netbox_data_tool  
      Action Input: {{ 
        "api_url": "/api/circuits/providers/", 
        "payload": {{ 
          "name": "Bell Canada", 
          "slug": "bell" 
        }} 
      }}
    
    - To delete a provider called "Bell Canada":  
      Thought: I need to create a provider named 'Bell Canada' with the slug 'bell'.  
      Action: delete_netbox_data_tool  
      Action Input: {{ 
        "api_url": "/api/circuits/providers/", 
        "payload": {{ 
          "name": "Bell Canada",
          "slug": "bell" 
        }} 
      }}
    
    **Begin!**
    
    Question: {input}  
    
    {agent_scratchpad}
    
    '''
)
logging.info(f"🛠️ Registered tools: {[tool.name for tool in tools]}")
# ✅ Pass 'tool_names' and 'tools' to the agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt_template.partial(
        tool_names=tool_names,
        tools=tool_descriptions
    )
)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,
    verbose=True,  # Enable detailed logs
    max_iterations=50
)
logging.info("🚀 AgentExecutor initialized with tools.")