import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    """Initializes and returns the Gemini LLM."""
    # Ensure GOOGLE_API_KEY is in the environment
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY environment variable is not set.")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2, # Lower temperature for more deterministic code generation
        max_output_tokens=8192
    )
    return llm

def get_content_as_str(content) -> str:
    """Extracts string content from standard string or list of dicts (from Gemini 3.5)."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        return "".join(text_parts)
    return str(content)
