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
get_problems_tool = Tool(
    name="get_problems_tool",
    description="Fetch problems from ServiceNow based on query parameters.",
    func=lambda input_data: ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).get_records("problem", input_data)
)

def generate_ai_problem_description(short_description, troubleshooting_notes=""):
    """Use LLM to generate a structured and detailed problem description based on real data."""
    
    # If troubleshooting notes exist, prioritize real data over AI hallucination
    real_notes_section = f"\n**Troubleshooting Notes:** {troubleshooting_notes}" if troubleshooting_notes else ""
    
    prompt = f"""
    Given the following problem statement and any troubleshooting notes, generate a **detailed but structured** problem description.

    **Problem Statement (short description):**
    {short_description}

    {real_notes_section}

    **Example Expansions:**
    1️⃣ Short: "PC1 cannot ping PC2."
       Expanded: "PC1 (IP 10.10.10.100) is experiencing 100% packet loss when attempting to communicate with PC2 (IP 10.10.30.100). This suggests a possible routing issue, firewall misconfiguration, or network interface failure."

    2️⃣ Short: "VPN not connecting."
       Expanded: "Users are unable to establish a VPN connection. Authentication logs show failed attempts, possibly due to expired certificates or incorrect tunnel configurations."

    3️⃣ Short: "Web application slow."
       Expanded: "Users report slow load times on the internal web application hosted at 192.168.1.50. The issue persists across multiple networks and devices, indicating a backend performance issue."

    🚀 Generate a concise but **structured** problem description using **ONLY** the provided information:
    """

    try:
        llm_response = llm.invoke(prompt)

        # Extract response correctly, depending on the LangChain LLM return type
        if isinstance(llm_response, dict) and "text" in llm_response:
            description = llm_response["text"].strip()
        elif hasattr(llm_response, "content"):  # Handle OpenAI response object
            description = llm_response.content.strip()
        else:
            description = str(llm_response).strip()

    except Exception as e:
        logging.error(f"⚠️ LLM error generating problem description: {e}")
        description = short_description  # Fallback to short description

    logging.info(f"📝 Generated Problem Description: {description}")  # Debugging log

    return description

def validate_problem_payload(input_data):
    """Validates the problem payload before sending to ServiceNow."""
    parsed_data = parse_json_input(input_data)

    short_desc = parsed_data.get("short_description", "").strip()

    # Check if the short description is missing or default
    if not short_desc or short_desc == "DEFAULT: Missing problem statement":
        logging.error("🚨 Invalid problem submission: Missing or default short description")
        return False, "Invalid problem: Missing or default short description."

    return True, parsed_data

create_problem_tool = Tool(
    name="create_problem_tool",
    description="Create a new problem in ServiceNow with required fields, ensuring short_description is valid.",
    func=lambda input_data: (
        ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD).create_record(
            "problem",
            {
                "short_description": parse_json_input(input_data).get("short_description", "DEFAULT: Missing problem statement"),
                "description": generate_ai_problem_description(
                    parse_json_input(input_data).get("short_description", ""),
                    parse_json_input(input_data).get("troubleshooting_notes", "")
                ),
                "category": parse_json_input(input_data).get("category", "Network"),
                "subcategory": parse_json_input(input_data).get("subcategory", "Connectivity"),
                "impact": parse_json_input(input_data).get("impact", "2"),
                "urgency": parse_json_input(input_data).get("urgency", "2"),
                "priority": parse_json_input(input_data).get("priority", "4"),
                "problem_state": "101",
            }
        ) if validate_problem_payload(input_data)[0] else {"error": validate_problem_payload(input_data)[1]}
    )
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

def get_problem_details(problem_number):
    """Fetch detailed problem information from ServiceNow."""
    servicenow = ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD)

    query_params = {"sysparm_query": f"number={problem_number}"}
    result = servicenow.get_records("problem", query_params)

    if "result" in result and len(result["result"]) > 0:
        return json.dumps(result["result"][0], indent=2)  # Convert to readable JSON format

    return "Problem details not found."

# Function to generate AI-based resolution notes
def generate_ai_resolution(problem_number):
    """Use LLM to generate a detailed resolution based on problem details."""
    problem_details = get_problem_details(problem_number)

    # Construct a prompt for LLM to generate a resolution reason
    prompt = f"""
    Given the following problem report, generate a **concise and structured** resolution statement.

    **Problem Details:**
    {problem_details}

    **Resolution Instructions:**
    - Clearly describe the root cause.
    - Outline the exact steps taken to fix the problem.
    - Use network-related terminology if applicable.
    - Keep it professional and to the point.

    **Example Resolutions:**
    1️⃣ "The router interface was administratively shut down. We issued 'no shutdown' to bring it up."
    2️⃣ "BGP peering was down due to a misconfigured ASN. Corrected ASN and reset the session."
    3️⃣ "Firewall ACLs were blocking traffic. Adjusted rule 101 to allow ICMP between PC1 and PC2."

    🚀 Generate a **concise** but **accurate** resolution statement:
    """

    try:
        llm_response = llm.invoke(prompt)
        resolution = llm_response.content.strip() if hasattr(llm_response, "content") else str(llm_response).strip()
    except Exception as e:
        logging.error(f"LLM error generating resolution: {e}")
        resolution = "Resolved with AI automation."  # Fallback message

    return resolution

# Function to transition a problem ticket through resolution
def transition_problem_state(problem_number, resolution_notes=None):
    """Ensure the problem follows correct state transitions and uses AI-generated resolutions."""
    servicenow = ServiceNowController(SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD)
    sys_id = get_problem_sys_id(problem_number)

    if not sys_id:
        return {"error": f"Problem {problem_number} not found"}

    logging.info(f"✅ Found sys_id: {sys_id} for problem {problem_number}")

    # Step 1: Move to "In Progress"
    servicenow.update_record("problem", sys_id, {
        "problem_state": "3",
        "state": "In Progress",
        "assigned_to": SERVICENOW_USER,
        "work_notes": f"Problem {problem_number} moved to 'In Progress' for resolution."
    })

    # Step 2: Generate AI-powered resolution reason
    resolution_notes = resolution_notes or generate_ai_resolution(problem_number)

    servicenow.update_record("problem", sys_id, {
        "problem_state": "6",
        "state": "Resolved",
        "resolved_by": SERVICENOW_USER,
        "resolved_at": "2025-02-15 23:00:00",
        "resolution_code": "fix_applied",
        "resolution_notes": resolution_notes,
        "work_notes": f"Resolution applied: {resolution_notes}"
    })

    # Step 3: Move to "Closed"
    return servicenow.update_record("problem", sys_id, {
        "problem_state": "107",
        "state": "Closed",
        "active": "false",
        "close_code": "Solved (Permanently)",
        "close_notes": resolution_notes,
        "work_notes": f"Final closure details: {resolution_notes}"
    })

update_problem_tool = Tool(
    name="update_problem_tool",
    description="Update and close a problem in ServiceNow with an AI-generated resolution.",
    func=lambda input_data: transition_problem_state(
        parse_json_input(input_data).get("problem_id", ""),
        parse_json_input(input_data).get("resolution_notes")
    )
)

# Define the AI Agent
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.6)

tools = [get_problems_tool, create_problem_tool, update_problem_tool]

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

    ** Assistant must strictly return plain text with no markdown formatting. 
    ** Do NOT use **bold**, *italics*, `code blocks`, bullet points, or any special characters.
    ** Only return responses in raw text without any additional formatting.

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
    max_iterations=2500,
    max_execution_time=1800
)

logging.info("🚀 ServiceNow AgentExecutor initialized with tools.")

