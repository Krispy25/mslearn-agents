import base64
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


OUTPUT_DIR = Path("agent_outputs")


def get_output_path(filename):
    """Create a unique path for generated files."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    file_name = Path(filename).name
    stem = Path(file_name).stem or "output"
    suffix = Path(file_name).suffix
    output_path = OUTPUT_DIR / file_name

    counter = 1
    while output_path.exists():
        output_path = OUTPUT_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    return output_path


def save_bytes(file_bytes, filename):
    """Save binary content to a local file."""
    output_path = get_output_path(filename)
    with open(output_path, "wb") as file_handle:
        file_handle.write(file_bytes)
    return output_path


def save_image(image_data, filename):
    """Save base64 image data to a file."""
    return save_bytes(base64.b64decode(image_data), filename)


def main():
    load_dotenv()
    project_endpoint = os.environ.get("PROJECT_ENDPOINT")
    agent_name = os.environ.get("AGENT_NAME", "it-support-agent")

    if not project_endpoint:
        print("Error: PROJECT_ENDPOINT environment variable not set")
        return

    print("Connecting to Microsoft Foundry project...")
    credential = DefaultAzureCredential()

    # allow_preview=True is required to use agent_name in get_openai_client
    project_client = AIProjectClient(
        credential=credential,
        endpoint=project_endpoint,
        allow_preview=True,
    )

    # Point the OpenAI client directly at the agent's endpoint
    print(f"Loading agent: {agent_name}")
    openai_client = project_client.get_openai_client(agent_name=agent_name)
    print(f"Connected to agent: {agent_name}")

    print("\n" + "=" * 60)
    print("IT Support Agent Ready!")
    print("Ask questions, request data analysis, or get help.")
    print("Type 'exit' to quit.")
    print("=" * 60 + "\n")

    # Maintain conversation history for multi-turn
    conversation_history = []
    image_count = 0

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})

        print("\n[Agent is thinking...]")
        try:
            response = openai_client.responses.create(
                model="gpt-4.1-mini",
                input=conversation_history,
            )
        except Exception as e:
            print(f"[Error during agent run: {e}]")
            conversation_history.pop()  # remove failed message
            continue

        handled_output = False

        for item in response.output or []:
            item_type = getattr(item, "type", "")

            if item_type == "message":
                for content_item in getattr(item, "content", []):
                    content_type = getattr(content_item, "type", "")

                    if content_type == "output_text":
                        text = getattr(content_item, "text", "")
                        if text:
                            print(f"\nAgent: {text}\n")
                            # Add assistant reply to history
                            conversation_history.append({"role": "assistant", "content": text})
                            handled_output = True

                    elif content_type == "image":
                        image_count += 1
                        filename = f"chart_{image_count}.png"
                        img_data = getattr(getattr(content_item, "image", None), "data", None)
                        if img_data:
                            file_path = save_image(img_data, filename)
                            print(f"\n[Agent generated a chart - saved to: {file_path}]")
                        else:
                            print("\n[Agent generated an image]")
                        handled_output = True

            elif item_type == "image":
                image_count += 1
                filename = f"chart_{image_count}.png"
                img_data = getattr(getattr(item, "image", None), "data", None)
                if img_data:
                    file_path = save_image(img_data, filename)
                    print(f"\n[Agent generated a chart - saved to: {file_path}]")
                else:
                    print("\n[Agent generated an image]")
                handled_output = True

        # Fallback: output_text shortcut on the response object
        if not handled_output:
            text = getattr(response, "output_text", None)
            if text:
                print(f"\nAgent: {text}\n")
                conversation_history.append({"role": "assistant", "content": text})
                handled_output = True

        if not handled_output:
            print("[No output received from agent]")


if __name__ == "__main__":
    main()