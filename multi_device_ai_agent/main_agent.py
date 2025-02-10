import os
import json
import logging
import streamlit as st
from tempfile import NamedTemporaryFile
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import urllib3
from R1_agent import tools as r1_tools, prompt_template as r1_prompt
from R2_agent import tools as r2_tools, prompt_template as r2_prompt
from SW1_agent import tools as sw1_tools, prompt_template as sw1_prompt
from SW2_agent import tools as sw2_tools, prompt_template as sw2_prompt
from PC1_agent import tools as pc1_tools, prompt_template as pc1_prompt
from PC2_agent import tools as pc2_tools, prompt_template as pc2_prompt

from netbox_agent import tools as netbox_tools, prompt_template as netbox_prompt
from email_agent import send_email_tool  
from image_agent import process_image_analysis  

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

llm = ChatOpenAI(model_name="gpt-4o", temperature="0.6")

# Initialize sub-agents
r1_agent = initialize_agent(tools=r1_tools, llm=llm, agent='zero-shot-react-description', prompt=r1_prompt, verbose=True)
r2_agent = initialize_agent(tools=r2_tools, llm=llm, agent='zero-shot-react-description', prompt=r2_prompt, verbose=True)
sw1_agent = initialize_agent(tools=sw1_tools, llm=llm, agent='zero-shot-react-description', prompt=sw1_prompt, verbose=True)
sw2_agent = initialize_agent(tools=sw2_tools, llm=llm, agent='zero-shot-react-description', prompt=sw2_prompt, verbose=True)
netbox_agent = initialize_agent(tools=netbox_tools, llm=llm, agent='structured-chat-zero-shot-react-description', prompt=netbox_prompt, verbose=True)
pc1_agent = initialize_agent(tools=pc1_tools, llm=llm, agent='zero-shot-react-description', prompt=pc1_prompt, verbose=True)
pc2_agent = initialize_agent(tools=pc2_tools, llm=llm, agent='zero-shot-react-description', prompt=pc2_prompt, verbose=True)

# Agent functions
def r1_agent_func(input_text: str) -> str:
    return r1_agent.invoke(f"R1: {input_text}")

def r2_agent_func(input_text: str) -> str:
    return r2_agent.invoke(f"R2: {input_text}")

def sw1_agent_func(input_text: str) -> str:
    return sw1_agent.invoke(f"SW1: {input_text}")

def sw2_agent_func(input_text: str) -> str:
    return sw2_agent.invoke(f"SW2: {input_text}")

def pc1_agent_func(input_text: str) -> str:
    return pc1_agent.invoke(f"PC1: {input_text}")

def pc2_agent_func(input_text: str) -> str:
    return pc1_agent.invoke(f"PC2: {input_text}")

def netbox_agent_func(input_text: str) -> str:
    return netbox_agent.invoke(f"NetBox: {input_text}")

def email_agent_func(input_data) -> dict:
    """Sends an email report via the email agent."""
    try:
        if isinstance(input_data, str):
            input_data = json.loads(input_data)
        if not isinstance(input_data, dict) or not all(k in input_data for k in ["recipient", "subject", "message"]):
            return {"status": "error", "error": "Invalid email data format"}
        return send_email_tool.func(input_data)
    except Exception as e:
        return {"status": "error", "error": str(e)}

def image_agent_func(input_data):
    """
    Processes an image along with a text prompt for multimodal AI.
    """
    # ✅ Fix: Ensure correct keys exist
    if not isinstance(input_data, dict) or "image_path" not in input_data or "user_prompt" not in input_data:
        return "Invalid image analysis request. Missing 'image_path' or 'user_prompt'."

    return process_image_analysis(
        image_path=input_data["image_path"],  # ✅ Correct parameter name
        user_prompt=input_data["user_prompt"]
    )

# Define LangChain Tools
r1_tool = Tool(name="R1 Agent", func=r1_agent_func, description="Use for Router R1 commands.")
r2_tool = Tool(name="R2 Agent", func=r2_agent_func, description="Use for Router R2 commands.")
sw1_tool = Tool(name="SW1 Agent", func=sw1_agent_func, description="Use for Switch SW1 commands.")
sw2_tool = Tool(name="SW2 Agent", func=sw2_agent_func, description="Use for Switch SW2 commands.")
netbox_tool = Tool(name="NetBox Agent", func=netbox_agent_func, description="Use for NetBox operations and queries.")
email_tool = Tool(name="Email Agent", func=email_agent_func, description="Send an email with 'recipient', 'subject', and 'message'.")
image_tool = Tool(name="Image Analysis Agent", func=image_agent_func, description="Analyze an image based on a user prompt.")
pc1_tool = Tool(name="PC1 Agent", func=pc1_agent_func, description="Use for Linux commands on PC1.")
pc2_tool = Tool(name="PC2 Agent", func=pc2_agent_func, description="Use for Linux commands on PC2.")

# Create Master Agent
master_tools = [r1_tool, r2_tool, sw1_tool, sw2_tool, netbox_tool, email_tool, image_tool, pc1_tool, pc2_tool]
master_agent = initialize_agent(tools=master_tools, llm=llm, agent="zero-shot-react-description", verbose=True)

logging.info(f"Master agent initialized with tools: {[tool.name for tool in master_tools]}")

# ============================================================
# **Streamlit UI**
# ============================================================

# Define navigation pages
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Upload Image", "Chat with AI"])

# **PAGE 1: Image Upload**
if page == "Upload Image":
    st.title("Upload an Image for AI Analysis (Optional)")

    uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])

    if uploaded_image:
        # Save uploaded image
        temp_file = NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_file.write(uploaded_image.getbuffer())
        temp_image_path = temp_file.name

        # Store image path in session state
        st.session_state["image_path"] = temp_image_path
        st.success("✅ Image uploaded successfully. Proceed to Chat.")

# **PAGE 2: Chat with AI**
if page == "Chat with AI":
    st.title("Chat with the AI Agent")
    st.write("Ask network-related questions or analyze uploaded images.")

    user_input = st.text_area("Enter your question or description:")

    if st.button("Send"):
        if not user_input:
            st.warning("⚠️ Please enter a question.")
        else:
            input_data = user_input  # Start with user query

            # 🚀 Check if image exists & explicitly invoke Image Analysis Agent
            if "image_path" in st.session_state and st.session_state["image_path"]:
                image_path = st.session_state["image_path"]

                # ✅ Call the Image Analysis Agent **before** master_agent
                image_response = image_agent_func({"image_path": image_path, "user_prompt": user_input})

                # ✅ Format `input_data` to include the image analysis for `master_agent`
                input_data = f"{user_input}\n\n📷 Image Analysis:\n{image_response}"

                # Display Image
                st.image(image_path, caption="📷 Analyzed Image", use_container_width=True)

            # 🚀 Pass formatted input to `master_agent.invoke()`
            response = master_agent.invoke(input_data)

            # ✅ Extract only the relevant response content
            response_text = response.get("output", "No valid response received.")

            # ✅ Format and display output
            st.write(f"### **Question:** {user_input}")
            st.write(f"### **Response:** {response_text}")

            # Save conversation history
            if "conversation" not in st.session_state:
                st.session_state.conversation = []
            st.session_state.conversation.append({"role": "assistant", "content": response_text})