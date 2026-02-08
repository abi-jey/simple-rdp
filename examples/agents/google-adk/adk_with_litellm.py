import os
from asyncio import run
from asyncio import sleep
from contextlib import contextmanager
from datetime import datetime
from logging import getLogger
from pathlib import Path
from warnings import catch_warnings
from warnings import filterwarnings

from dotenv import load_dotenv
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import ResumabilityConfig
from google.adk.apps.app import App
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.multimodal_tool_results_plugin import MultimodalToolResultsPlugin
from google.adk.sessions import Session
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.genai.types import Content
from google.genai.types import FinishReason
from google.genai.types import Part
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from rich.logging import RichHandler

from simple_rdp import RDPClient
from simple_rdp.agentic_computer_use.google_adk import AdkExternalCompaction

load_dotenv()
logger = getLogger("adk_agent")

GoogleADKInstrumentor().instrument()

instruction = """
You are an Autonomous agent with a desktop computer. 
You need to share you thinking throughout the process.
First get the Machine Info like screen resolution and so on.
While permorming actions on screen you should calculate screen coordinates based on the screen resolution.
While pointer is on the text forms it might disapear and instead the bliker cursor will apear, be aware of that.
It's important to verify before click weather the mouse pointer is on the right place.
You can do this by taking pointer area screenshot.
Never assume that because you have typed something input actually inserted.
Verify this by pointer area or full screen screenshot.
"""


model = LiteLlm(
    model="openai/Kimi-k2.5",
    api_base="https://agent-test-abbas.cognitiveservices.azure.com/openai/v1",
    api_key=os.environ.get("AZURE_FOUNDRY_KEY", ""),
    max_retries=3,
)


def get_agent(tools: list) -> LlmAgent:
    before_call_back, after_call_back = get_call_backs()
    return LlmAgent(
        name="computer_use_agent",
        model=model,  # Or your preferred Gemini model
        instruction=instruction,
        description="An autonomous agent with Desktop Computer capabilities.",
        tools=tools,
        before_model_callback=[before_call_back],
        after_model_callback=[after_call_back],
    )


async def get_rdp_client() -> RDPClient:
    recoring_path = Path(".") / "sessions" / "google_adk_agent" / datetime.now().strftime("%Y%m%d_%H%M%S") / "recording"
    recoring_path.mkdir(exist_ok=True, parents=True)
    recoring_path = recoring_path / "0001.mp4"
    recoring_path = str(recoring_path)
    client = RDPClient(
        host=os.environ.get("RDP_HOST", ""),
        username=os.environ.get("RDP_USER", ""),
        password=os.environ.get("RDP_PASS", ""),
        show_wallpaper=True,
        record_to=recoring_path,
    )
    return client


async def main(question: str, session_id: str | None = None):
    user = "user123"
    app_name = "adk_agent"
    session_service = await get_session_service()

    rdp_client = await get_rdp_client()
    tools = rdp_client.get_agentic_tools(for_framework="google-adk")
    agent = get_agent(tools=tools)

    # We need to use app to enable MultimodalToolResultsPlugin which allows image + text responses
    app = App(
        name=app_name,
        root_agent=agent,
        plugins=[MultimodalToolResultsPlugin()],
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    async with rdp_client:  # Alternatively, you can do rdp_client.connect() and rdp_client.disconnect() manually
        runner = Runner(
            session_service=session_service,
            app=app,
        )
        session = await get_session(
            session_service=session_service,
            user_id=user,
            session_id=session_id,
            app_name=app_name,
        )
        compactor = AdkExternalCompaction(
            session_service=session_service,
            model=model,
            app_name=app_name,
            runner=runner,
            max_token_length=100_000,
        )
        adk_generator = compactor.run_async(
            user_id=user,
            session_id=session.id,
            new_message=Content(
                role="user",
                parts=[Part(text=question)],
            ),
        )
        async for response in adk_generator:
            if not response.finish_reason:
                continue
            if response.finish_reason == FinishReason.STOP:
                if not response.content:
                    logger.warning("Agent finished without a response.")
                    raise ValueError("Agent finished without a response.")
                if not response.content.parts:
                    logger.warning("Agent finished without a response.")
                    raise ValueError("Agent finished without a response.")
                result = ""
                n = len(response.content.parts)
                result += f"Agent response: {n}\n"
                for part in response.content.parts:
                    if part.function_call:
                        result += f"[dim green]Function Call:[/dim green]\n{part.function_call.name}"
                        result += f"({part.function_call.args})"
                        if part.function_call.partial_args:
                            result += f" with partial args: {part.function_call.partial_args}"
                        result += "\n"
                    if part.thought:
                        result += f"[dim yellow]Thought:[/dim yellow]\n{part.text}\n\n"
                    elif part.text:
                        result += f"[dim cyan]Text:[/dim cyan]\n{part.text}\n\n"
                stripped_result = result.strip("\n")
                logger.info(f"Agents response: [bold blue]\n\t{stripped_result}[/bold blue]\n\n")


async def get_session_service() -> DatabaseSessionService:
    return DatabaseSessionService(db_url="sqlite+aiosqlite:///./adk_agent_data.db")


async def get_session(
    session_service: DatabaseSessionService,
    user_id: str,
    *,
    session_id: str | None = None,
    app_name: str = "adk-agent",
) -> Session:
    if session_id is None:
        logger.info("No session ID provided. Creating a new session...")
        session = await session_service.create_session(app_name=app_name, user_id=user_id)
        logger.info(f"Created new session with ID: {session.id}")
        return session
    logger.info(f"Retrieving session with ID: {session_id}...")
    session = await session_service.get_session(app_name=app_name, session_id=session_id, user_id=user_id)
    if session:
        logger.info(f"Session found: {session.id}")
        return session
    raise ValueError(f"Session with ID {session_id} not found")


@contextmanager
def configure_logging():
    logging.basicConfig(level=logging.INFO, format="\\[%(name)s]: %(message)s", handlers=[RichHandler(markup=True)])
    adk_logger = getLogger("google_adk.google.adk.models.google_llm")
    adk_logger.setLevel(logging.WARNING)
    httpx_logger = getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    adk_logger = getLogger("google_adk.google.adk.sessions.database_session_service")
    adk_logger.setLevel(logging.WARNING)
    stat_logger = getLogger("simple_rdp.stats")
    stat_logger.setLevel(logging.WARNING)
    stat_logger = getLogger("simple_rdp.display.stats")
    stat_logger.setLevel(logging.WARNING)
    litellm_logger = getLogger("LiteLLM")
    litellm_logger.setLevel(logging.WARNING)
    with catch_warnings():
        filterwarnings("ignore", category=UserWarning, module="pydantic.*")
        yield


def configure_check_langfuse():
    # Check if Langfuse environment variables are set for logging
    lf_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    lf_secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    lf_base_url = os.environ.get("LANGFUSE_BASE_URL")
    if not lf_public_key or not lf_secret_key or not lf_base_url:
        return
    from langfuse import get_client

    langfuse = get_client()
    if langfuse.auth_check():
        logger.info("Langfuse client is authenticated and ready!")
    else:
        logger.warning("Authentication failed. Please check your credentials and host.")


def get_call_backs():
    path = Path(".") / "sessions" / "google_adk_agent" / datetime.now().strftime("%Y%m%d_%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    before_call_count = 0
    after_call_count = 0

    async def before_call_back(callback_context: CallbackContext, llm_request: LlmRequest) -> None:
        """We save model requests in session folder for later analysis if needed" """
        nonlocal before_call_count
        before_call_count += 1
        file_name = f"{str(before_call_count).zfill(5)}-request.json"
        file_path = path / file_name
        json_data = llm_request.model_dump_json(indent=2)
        file_path.write_text(json_data, encoding="utf-8")
        llm_request.model_dump_json(indent=2)

        logger.info(
            "[bold yellow]Waiting for a short moment before the next model call "
            "to avoid hitting rate limits...[/bold yellow]"
        )
        await sleep(2)
        return None

    async def after_call_back(callback_context: CallbackContext, llm_response: LlmResponse) -> None:
        nonlocal after_call_count
        after_call_count += 1
        file_name = f"{str(after_call_count).zfill(5)}-response.json"
        file_path = path / file_name
        json_data = llm_response.model_dump_json(indent=2)
        file_path.write_text(json_data, encoding="utf-8")
        return None

    return before_call_back, after_call_back


if __name__ == "__main__":
    import logging

    with configure_logging():
        configure_check_langfuse()
        question = (
            "Can you close the browser, open browser again and see navigate to google.com"
            "and create a gmail account for yourself? feel free to name yourself anything you like."
            "just let me know what your email is, note that this is order to prove your capabilities,"
            "I understand that creating a gmail account might have security implications, "
            "First we create and account and then wait for my further instructions to delete"
        )
        session_id = None  # Or set to an existing session ID to continue a conversation

        run(main(question, session_id))
