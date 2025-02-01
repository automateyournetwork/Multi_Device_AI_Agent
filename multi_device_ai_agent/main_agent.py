import os
import json
import logging
import streamlit as st
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI
#from langchain_community.llms import Ollama
import urllib3
from dotenv import load_dotenv

# Import the tools and prompt templates from your agent scripts
from R1_agent import tools as r1_tools, prompt_template as r1_prompt
from R2_agent import tools as r2_tools, prompt_template as r2_prompt
from SW1_agent import tools as sw1_tools, prompt_template as sw1_prompt
from SW2_agent import tools as sw2_tools, prompt_template as sw2_prompt
from netbox_agent import tools as netbox_tools, prompt_template as netbox_prompt  # Import NetBox agent
from email_agent import send_email_tool  # Import the email sending tool

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#llm = Ollama(model="command-r7b", base_url="http://ollama:11434")
llm = ChatOpenAI(model_name="gpt-4o", temperature="0.3")

# Initialize sub-agents for each device
r1_agent = initialize_agent(
    tools=r1_tools,
    llm=llm,
    agent='zero-shot-react-description',
    prompt=r1_prompt,
    verbose=True
)

r2_agent = initialize_agent(
    tools=r2_tools,
    llm=llm,
    agent='zero-shot-react-description',
    prompt=r2_prompt,
    verbose=True
)

sw1_agent = initialize_agent(
    tools=sw1_tools,
    llm=llm,
    agent='zero-shot-react-description',
    prompt=sw1_prompt,
    verbose=True
)

sw2_agent = initialize_agent(
    tools=sw2_tools,
    llm=llm,
    agent='zero-shot-react-description',
    prompt=sw2_prompt,
    verbose=True
)

# Initialize the NetBox agent
netbox_agent = initialize_agent(
    tools=netbox_tools,
    llm=llm,
    agent='zero-shot-react-description',
    prompt=netbox_prompt,
    verbose=True
)

def r1_agent_func(input_text: str) -> str:
    return r1_agent.invoke(f"R1: {input_text}")

def r2_agent_func(input_text: str) -> str:
    return r2_agent.invoke(f"R2: {input_text}")

def sw1_agent_func(input_text: str) -> str:
    return sw1_agent.invoke(f"SW1: {input_text}")

def sw2_agent_func(input_text: str) -> str:
    return sw2_agent.invoke(f"SW2: {input_text}")

def netbox_agent_func(input_text: str) -> str:
    return netbox_agent.invoke(f"NetBox: {input_text}")

def email_agent_func(input_data) -> dict:
    """
    Calls the email agent to send an email.
    Expects a dictionary with 'recipient', 'subject', and 'message' keys.
    """
    try:
        # Ensure input_data is a dictionary
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)  # Attempt to parse JSON string
            except json.JSONDecodeError:
                return {"status": "error", "error": "Invalid JSON input. Expected a dictionary."}

        if not isinstance(input_data, dict):
            return {"status": "error", "error": "Input data must be a dictionary."}

        # Validate required fields
        required_fields = ["recipient", "subject", "message"]
        missing_fields = [field for field in required_fields if field not in input_data]
        if missing_fields:
            return {"status": "error", "error": f"Missing required fields: {', '.join(missing_fields)}"}

        return send_email_tool.func(input_data)

    except Exception as e:
        return {"status": "error", "error": str(e)}

# Define tools for each sub-agent
r1_tool = Tool(name="R1 Agent",
               func=r1_agent_func,
               description="Use for Router R1 commands.")
r2_tool = Tool(name="R2 Agent",
               func=r2_agent_func,
               description="Use for Router R2 commands.")
sw1_tool = Tool(name="SW1 Agent",
                func=sw1_agent_func,
                description="Use for Switch SW1 commands.")
sw2_tool = Tool(name="SW2 Agent",
                func=sw2_agent_func,
                description="Use for Switch SW2 commands.")
netbox_tool = Tool(name="NetBox Agent",
                func=netbox_agent_func,
                description="Use for NetBox operations and queries.")
email_tool = Tool(
    name="Email Agent",
    func=email_agent_func,  # ✅ Using the updated function
    description="Send an email with 'recipient', 'subject', and 'message'."
)

# Create the master tool list
master_tools = [r1_tool, r2_tool, sw1_tool, sw2_tool, netbox_tool, email_tool]

master_agent = initialize_agent(
    tools=master_tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True
)

logging.info(f"Master agent initialized with tools: {[tool.name for tool in master_tools]}")

# ============================================================
# Streamlit UI
# ============================================================

# Set up Streamlit UI
st.title("Infrastructure as Agents - Cisco IOS")
st.write("Operate your network with natural language")

user_input = st.text_input("Enter your question:")

# Initialize chat state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = ""

if "conversation" not in st.session_state:
    st.session_state.conversation = []

# Button to send input
if st.button("Send"):
    if user_input:
        st.session_state.conversation.append({"role": "user", "content": user_input})

        try:
            # 🚀 Invoke the master agent
            response = master_agent.invoke(user_input)

            # Display results
            st.write(f"**Question:** {user_input}")
            st.write(f"**Answer:** {response}")

            # Update conversation history
            st.session_state.conversation.append({"role": "assistant", "content": response})
            st.session_state.chat_history = "\n".join(
                [f"{entry['role'].capitalize()}: {entry['content']}" for entry in st.session_state.conversation]
            )

        except Exception as e:
            st.write(f"An error occurred: {str(e)}")

# Display conversation history
if st.session_state.conversation:
    st.write("## Conversation History")
    for entry in st.session_state.conversation:
        st.write(f"**{entry['role'].capitalize()}:** {entry['content']}")
