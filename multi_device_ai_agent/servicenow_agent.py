import os
import json
import logging
import requests
from dotenv import load_dotenv
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
import urllib3

# Load environment variables from .env file
load_dotenv()
SERVICENOW_URL = os.getenv("SERVICENOW_URL").rstrip('/')
SERVICENOW_USER = os.getenv("SERVICENOW_USER")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")

# Configure logging
logging.basicConfig(level=logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ServiceNowController for Incident and Problem Management
class ServiceNowController:
    def __init__(self, servicenow_url, username, password):
        self.servicenow = servicenow_url.rstrip('/')
        self.auth = (username, password)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def get_records(self, table, query_params=None):
        """Retrieve records from a specified ServiceNow table."""
        url = f"{self.servicenow}/api/now/table/{table}"
        logging.info(f"GET Request to URL: {url}")
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers, params=query_params, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"GET request failed: {e}")
            return {"error": f"Request failed: {e}"}
    
    def create_record(self, table, payload):
        """Create a new record in a specified ServiceNow table."""
        url = f"{self.servicenow}/api/now/table/{table}"
        logging.info(f"POST Request to URL: {url} with Payload: {json.dumps(payload, indent=2)}")
        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, json=payload, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"POST request failed: {e}")
            return {"error": f"Request failed: {e}"}
    
    def update_record(self, table, record_sys_id, payload):
        """Update a record in a specified ServiceNow table."""
        url = f"{self.servicenow}/api/now/table/{table}/{record_sys_id}"
        logging.info(f"PATCH Request to URL: {url} with Payload: {json.dumps(payload, indent=2)}")
        try:
            response = requests.patch(url, auth=self.auth, headers=self.headers, json=payload, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"PATCH request failed: {e}")
            return {"error": f"Request failed: {e}"}

def parse_json_input(input_data):
    """Ensure input_data is a dictionary. If it's a string, try to parse it as JSON."""
    if isinstance(input_data, str):
        try:
            return json.loads(input_data)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error: {e} | Received input: {input_data}")
            return {"error": "Invalid JSON format received"}
    return input_data

# Define LangChain Tools
get_incidents_tool = Tool(
    name="get_incidents_tool",
    description="Fetch incidents from ServiceNow based on query parameters.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).get_records("incident", input_data)
)

create_incident_tool = Tool(
    name="create_incident_tool",
    description="Create a new incident in ServiceNow.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).create_record("incident", input_data)
)

update_incident_tool = Tool(
    name="update_incident_tool",
    description="Update an existing incident in ServiceNow using its sys_id.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).update_record(
        "incident",  # ✅ Corrected from "problem" to "incident"
        parse_json_input(input_data).get('sys_id', ''),
        parse_json_input(input_data).get('payload', {})
    )
)
get_problems_tool = Tool(
    name="get_problems_tool",
    description="Fetch problems from ServiceNow based on query parameters.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).get_records("problem", input_data)
)

create_problem_tool = Tool(
    name="create_problem_tool",
    description="Create a new problem in ServiceNow.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).create_record("problem", input_data)
)

def get_problem_sys_id(problem_number):
    """Get the sys_id for a problem based on its number"""
    query_params = {"sysparm_query": f"number={problem_number}"}
    result = ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).get_records("problem", query_params)
    
    if "result" in result and len(result["result"]) > 0:
        return result["result"][0]["sys_id"]
    return None

def get_problem_state(sys_id):
    """Retrieve the current state of a problem"""
    query_params = {"sysparm_query": f"sys_id={sys_id}", "sysparm_fields": "problem_state"}
    result = ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).get_records("problem", query_params)
    
    if "result" in result and len(result["result"]) > 0:
        return result["result"][0]["problem_state"]
    return None

def transition_problem_state(problem_number, resolution_notes):
    """Ensure the problem follows the correct state transitions"""
    servicenow = ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD)
    sys_id = get_problem_sys_id(problem_number)

    if not sys_id:
        return {"error": f"Problem {problem_number} not found"}

    logging.info(f"✅ Found sys_id: {sys_id} for problem {problem_number}")

    # Step 1: Move to "In Progress"
    logging.info(f"🔄 Moving problem {problem_number} to 'In Progress'...")
    servicenow.update_record("problem", sys_id, {
        "problem_state": "3",
        "state": "In Progress",
        "assigned_to": SERVICENOW_USER
    })

    # Step 2: Move to "Resolved"
    logging.info(f"✅ Marking problem {problem_number} as 'Resolved'...")
    servicenow.update_record("problem", sys_id, {
        "problem_state": "6",
        "state": "Resolved",
        "resolved_by": SERVICENOW_USER,
        "resolved_at": "2025-02-15 23:00:00",
        "resolution_code": "fix_applied",
        "resolution_notes": resolution_notes,
        "work_notes": f"Resolution: {resolution_notes}"
    })

    # Step 3: Move to "Closed"
    logging.info(f"✅ Closing problem {problem_number}...")
    response = servicenow.update_record("problem", sys_id, {
        "problem_state": "107",
        "state": "Closed",
        "active": "false",
        "close_code": "Solved (Permanently)",
        "close_notes": resolution_notes,
        "work_notes": f"Closing issue: {resolution_notes}"
    })

    return response

update_problem_tool = Tool(
    name="update_problem_tool",
    description="Update and close a problem in ServiceNow following the correct workflow.",
    func=lambda input_data: transition_problem_state(
        parse_json_input(input_data).get("sys_id", ""),
        parse_json_input(input_data).get("resolution_notes", "Resolved by automation.")
    )
)

# Define the AI Agent
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.6)

tools = [get_incidents_tool, create_incident_tool, update_incident_tool, get_problems_tool, create_problem_tool, update_problem_tool]

prompt_template = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tool_names", "tools"],
    template='''
    You are a ServiceNow assistant managing incidents and problems.
    
    **TOOLS:**  
    {tools}

    **Available Tool Names:**  
    {tool_names}
    
    **Problem Resolution Workflow:**  
    1️⃣ **Move to "In Progress"** before resolving  
    2️⃣ **Move to "Resolved"** with a resolution note  
    3️⃣ **Move to "Closed"** with confirmation 

    **FORMAT:**  
    Thought: [Your reasoning]  
    Action: [Tool Name]  
    Action Input: {{ "table": "incident" or "problem", "sysparm_query": "active=true", "sysparm_limit": "10" }}  
    Observation: [Result]  
    Final Answer: [Answer to the User]  

    **Examples:**
    - To get open incidents:  
      Thought: I need to retrieve all open incidents.  
      Action: get_incidents_tool  
      Action Input: {{ "sysparm_query": "active=true", "sysparm_limit": "10" }}
              
    - To create a new incident:  
      Thought: I need to create a high-priority incident.  
      Action: create_problem_tool  
      Action Input: {{ "short_description": "Server Down", "priority": "1" }}  

    - To check open problems:  
      Thought: I need to retrieve all open problems.  
      Action: get_problems_tool  
      Action Input: {{ "sysparm_query": "active=true", "sysparm_limit": "10" }}  
      
    - To close a resolved problem:  
      Thought: This problem has been fixed and confirmed. I should close it.  
      Action: update_problem_tool  
      Action Input: {{ "sys_id": "SYS_ID_123", "problem_state": "107", "state": "Closed", "close_notes": "Issue resolved and verified." }}  

    - Thought: This problem must be transitioned through the correct states before closing.
    - Action: `update_problem_tool`
    - Action Input: `{{ "sys_id": "PRB0040004", "resolution_notes": "Interface Ethernet0/0.10 was down, restored it." }}`        
          
    **Now, begin handling requests!**  

    Question: {input} 
     
    {agent_scratchpad}
    '''
)

agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt_template.partial(
        tool_names=", ".join([tool.name for tool in tools]),
        tools="\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    )
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,
    verbose=True,
    max_iterations=50
)

logging.info("🚀 ServiceNow AgentExecutor initialized with tools.")

