import os
import logging
from openai import OpenAI
from langchain.tools import Tool
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load OpenAI API Key from Environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def image_to_base64(image_path):
    """
    Convert an image file to base64 encoding.
    
    Args:
        image_path (str): The path to the image file.

    Returns:
        str: The base64-encoded image data.
    """
    if not image_path:
        logging.error("❌ Error: image_path is None or empty.")
        return None

    try:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
            base64_encoded = base64.b64encode(img_data).decode('utf-8')
            logging.info("✅ Image successfully encoded to base64.")
            return base64_encoded
    except FileNotFoundError:
        logging.error(f"❌ Error: File not found - {image_path}")
        return None
    except Exception as e:
        logging.error(f"❌ Error converting image to base64: {str(e)}")
        return None

def process_image_analysis(image_path: str, user_prompt: str):
    """
    Sends the user's text prompt along with an uploaded image (converted to base64) to OpenAI's GPT-4o model.

    Args:
        image_path (str): The local path to the uploaded image.
        user_prompt (str): The user's text prompt describing what they want to analyze.

    Returns:
        str: The AI-generated response based on the image and prompt.
    """
    if not image_path:
        return "Error: No image was provided."

    # Convert image to base64
    image_base64 = image_to_base64(image_path)
    
    if not image_base64:
        return "Error: Unable to convert image to base64."

    logging.info(f"🔍 Processing image: {image_path} with prompt: {user_prompt}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o", temperature="0.6",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"  # ✅ Correct base64 format
                            }
                        },
                    ],
                }
            ]
        )

        result = response.choices[0].message.content
        logging.info(f"✅ AI Response: {result}")
        return result

    except Exception as e:
        logging.error(f"❌ Error processing image: {str(e)}")
        return f"Error: {str(e)}"

# Define LangChain Tool for Image Analysis
image_analysis_tool = Tool(
    name="Image Analysis Agent",
    func=lambda input_data: process_image_analysis(
        image_path=input_data.get("image_path"),
        user_prompt=input_data.get("user_prompt"),
    ),
    description="Analyzes an image based on a provided user prompt. Requires 'image_path' and 'user_prompt'."
)

logging.info("🖼️ Image Analysis Agent Initialized")
