Multi_Device_AI_Agent

Extend AI Agents to manage and interact with a full network topology of devices using Cisco Modeling Labs (CML).

🚀 Features

AI-driven interaction with multiple network devices (routers and switches)

Support for dynamic command execution and configuration management

Streamlit-based UI for seamless interaction

📦 Installation

Clone the Repository:

git clone [<repository-url>](https://github.com/automateyournetwork/Multi_Device_AI_Agent)
cd Multi_Device_AI_Agent

Configure Environment Variables:

Create a .env file in the project root.

Add your OpenAI API Key:

OPENAI_API_KEY=your_openai_api_key_here

⚠️ Currently, this project only supports OpenAI models. Open-source model integration is in progress!

Configure Your Network Topology:

Update testbed.yaml with your custom network topology.

OR use the Cisco DevNet Always-On Cisco Modeling Labs (CML) Sandbox.

Launch the Application:

docker-compose up

Access the Web Interface:

Open your browser and visit: http://localhost:8501

💡 How to Use

Enter natural language commands to interact with your network devices.

Configure routers and switches, run show commands, or explore advanced use cases.

Experiment freely with your CML topology or your custom environment.

🛠️ Customization

Add New Devices:

Update the testbed.yaml file with additional devices.

Define custom tools and agents in R1_agent.py, R2_agent.py, SW1_agent.py, and SW2_agent.py.

Modify Tools and Prompts:

Customize command behaviors and responses in the agent scripts.

🔧 Troubleshooting

Agent Keeps Connecting to the Wrong Device:

Ensure device names are correctly defined in testbed.yaml.

Verify proper use of apply_configuration_tool without including configure terminal in commands.

Docker Issues:

Run docker-compose down && docker-compose up --build to rebuild containers.

📖 Roadmap

✅ Multi-device support for routers and switches

🔄 Open-source model integration

⚡ Enhanced error handling and logging

🧠 Smarter device targeting and context awareness

🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change. Thanks - John