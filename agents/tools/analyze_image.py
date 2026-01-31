import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()


def analyze_file(file_path: str) -> None:
    # Initialize the client
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set. Add it to .env file.")
    client = genai.Client(api_key=api_key)

    try:
        # 1. Upload the file to the Gemini File API
        print(f"Uploading {file_path}...")
        uploaded_file = client.files.upload(file=file_path)

        # 2. Generate content based on the file
        print("Analyzing...")
        prompt = (
            "This is a screenshot from an RDP (Remote Desktop Protocol) client. "
            "Please analyze if the image looks correct or if there are any visual "
            "artifacts, corruption, color issues, or rendering problems. "
            "Describe what you see in detail, including any issues with the display."
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[uploaded_file, prompt],
        )

        # 3. Print the result
        print("\n--- Analysis Result ---")
        print(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Accept path from command line or use default
    path_to_analyze = sys.argv[1] if len(sys.argv) > 1 else "screenshot_final.png"

    if os.path.exists(path_to_analyze):
        analyze_file(path_to_analyze)
    else:
        print(f"Error: The specified file path does not exist: {path_to_analyze}")
