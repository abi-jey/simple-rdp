import base64
import multiprocessing
from asyncio import sleep
from asyncio import to_thread
from collections.abc import Callable
from collections.abc import Coroutine
from io import BytesIO
from logging import getLogger
from queue import Empty as QueueEmpty
from typing import TYPE_CHECKING
from typing import Any
from typing import Union

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.event_actions import EventCompaction
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import Session
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content
from google.genai.types import FinishReason
from google.genai.types import Part

logger = getLogger(__name__)


def _extract_conversation_history(events: list["Event"]) -> str:
    """
    Extract conversation history from events as a plain string.
    This function is used to prepare data for the subprocess.
    """
    conversation_history = ""
    for event in events:
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if part.text:
                if part.thought:
                    conversation_history += f"\n[Thought: {part.text}]\n"
                else:
                    conversation_history += part.text
            if part.function_call:
                conversation_history += (
                    f"\n[Function call: {part.function_call.name} with args {part.function_call.args}]\n"
                )
    return conversation_history


def _generate_summary_in_process(prompt: str, model_config: dict[str, Any]) -> str:
    """
    Standalone function that runs in a separate process to generate a summary.
    Takes a string prompt and model configuration dict, returns a string summary.

    This function must be defined at module level to be picklable for multiprocessing.

    Args:
        prompt: The full prompt string to send to the model
        model_config: Dictionary containing model configuration:
            - model: str - The model name/identifier
            - api_base: str | None - API base URL (optional)
            - api_key: str | None - API key (optional)
            - app_name: str - Application name for the session
    """
    import asyncio

    async def _async_generate_summary() -> str:
        # Import inside function to ensure clean process state
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.runners import Runner
        from google.genai.types import Content
        from google.genai.types import Part

        # Reconstruct the model from config
        model_name = model_config.get("model", "")
        api_base = model_config.get("api_base")
        api_key = model_config.get("api_key")
        app_name = model_config.get("app_name", "compaction_agent")

        # Create LiteLlm model with the same configuration as the parent
        model: LiteLlm | str = (
            LiteLlm(model=model_name, api_base=api_base, api_key=api_key) if api_base or api_key else model_name
        )

        _agent = LlmAgent(
            name="summarizer_agent",
            model=model,
            instruction="",
            description="Summarizer",
        )
        _session_service = InMemorySessionService()
        _new_session = await _session_service.create_session(
            app_name=app_name,
            user_id="compaction_agent",
        )
        runner = Runner(session_service=_session_service, agent=_agent, app_name=app_name)

        async for response in runner.run_async(
            user_id="compaction_agent",
            session_id=_new_session.id,
            new_message=Content(role="user", parts=[Part(text=prompt)]),
        ):
            if (
                response.content
                and response.content.parts
                and response.content.parts[-1].text
                and response.finish_reason == FinishReason.STOP
            ):
                return str(response.content.parts[-1].text)

        return ""

    result: str = asyncio.run(_async_generate_summary())
    return result


def _process_target(prompt: str, model_config: dict[str, Any], result_queue: "multiprocessing.Queue[str]") -> None:
    """
    Target function for the summary generation subprocess.
    Must be defined at module level to be picklable for multiprocessing.
    """
    try:
        result = _generate_summary_in_process(prompt, model_config)
        result_queue.put(result)
    except Exception:
        result_queue.put("")


if TYPE_CHECKING:
    from simple_rdp import RDPClient
# Type alias for async tool functions with varying signatures
AgenticTool = Callable[..., Coroutine[object, object, list[Part] | str]]


def wrap_client_methods_for_google_adk(client: "RDPClient", log_reasoning: bool = False) -> list[AgenticTool]:
    """
    Wraps RDPClient methods as Google ADK tools.

    This allows the RDPClient's functionality to be used within a Google ADK agent.
    Each tool is a wrapper around an RDPClient method, allowing it to be called by the agent.
    The tools are designed to be compatible with Google ADK's expectations for tool interfaces.
    """
    tools: list[AgenticTool] = []

    async def screenshot() -> list[Part]:
        """Get a screenshot of the display"""
        img_pil = await client.screenshot()
        img_bytes = BytesIO()
        img_pil.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        # img_b64 = base64.b64encode(img_bytes.read()).decode("utf-8")
        return [Part.from_bytes(data=img_bytes.read(), mime_type="image/jpeg")]

    tools.append(screenshot)

    async def pointer_area_screenshot() -> list[Part]:
        """Get a screenshot of the area around the pointer
        Returns an image along with the coordinates of the top-left and bottom-right corners of the screenshot area.
        """
        img_pil, top_left_coords, bottom_right_coords = await client.pointer_area_screenshot()
        img_bytes = BytesIO()
        img_pil.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        img_b64 = base64.b64encode(img_bytes.read()).decode("utf-8")
        caption = (
            f"Top-left: {top_left_coords[0], top_left_coords[1]}, "
            f"Bottom-right: {bottom_right_coords[0], bottom_right_coords[1]}"
        )
        return [Part.from_uri(file_uri=f"data:image/jpeg;base64,{img_b64}"), Part.from_text(text=caption)]

    tools.append(pointer_area_screenshot)

    async def mouse_move(x: int, y: int) -> str:
        """Move the mouse pointer to the specified (x, y) coordinates."""
        await client.mouse_move(x, y)
        return f"Moved mouse to ({x}, {y})"

    tools.append(mouse_move)

    async def mouse_click(double: bool = False, button: str = "left") -> str:
        """
        Click the mouse at the current pointer position.
        if double is True, perform a double click. default is single click.
        The button parameter can be "left", "right", or "middle". default is "left".
        """
        translated_button = {
            "left": 1,
            "right": 2,
            "middle": 3,
        }.get(button.lower(), 1)
        mouse_coords = client.pointer_position
        await client.mouse_click(mouse_coords[0], mouse_coords[1], double_click=double, button=translated_button)
        return f"Clicked at ({mouse_coords[0]}, {mouse_coords[1]})"

    tools.append(mouse_click)

    async def send_text(text: str) -> str:
        """Send keyboard input as text."""
        await client.send_text(text)
        return f"Sent text: {text}"

    tools.append(send_text)

    async def send_key(key: str) -> str:
        await client.send_key(key)
        return f"Sent key: {key}"

    send_key.__doc__ = client.send_key.__doc__  # Append the original docstring from RDPClient's send_key method
    tools.append(send_key)

    async def wait(seconds: int) -> str:
        """Wait for a specified number of seconds."""
        await sleep(seconds)
        return f"Waited for {seconds} seconds."

    tools.append(wait)

    async def get_machine_info() -> str:
        """Get machine information such as screen resolution."""
        info = await client.get_computer_info()
        return info

    tools.append(get_machine_info)
    return tools


class AdkExternalCompaction:
    """
    Configuration for compacting events in Google ADK.

    """

    def __init__(
        self,
        *,
        session_service: "BaseSessionService",
        model: Union[str, "BaseLlm"],
        runner: Runner,
        app_name: str,
        max_token_length: int = 30000,
    ):
        self.session_service = session_service
        self.model = model
        self.runner = runner
        self.prompt_template = (
            "Summarize the follwing list of events/actions performed by an autonomous agent, Don't leave"
            " Critical details that are important for continuation,"
            " Describe the current state + what is expected to be done next. at the end also add original request not"
            " To let it leave our sight"
            " For tools, and their usage, please include all details (don't summarize), use exact names \n"
            " below are list of events/actions:"
        )
        self.app_name = app_name
        self.max_token_length = max_token_length
        self.session_id: str | None = None
        self.user_id: str | None = None

        try:
            import google.adk.agents  # noqa: F401
        except ImportError as err:
            raise ImportError(
                "google-adk package is required for AdkExternalCompaction. "
                "Please install it with 'pip install google-adk'."
            ) from err

    async def should_compact(self) -> bool:
        """
        goes over all events after the last compactions and does different checks
        """
        if self.session_id is None or self.user_id is None:
            logger.warning("Session ID or User ID is not set for compaction, skipping compaction check.")
            return False
        session = await self.session_service.get_session(
            app_name=self.app_name,
            session_id=self.session_id,
            user_id=self.user_id,
        )
        if not session:
            logger.warning(f"Session with ID {self.session_id} not found for compaction check.")
            return False
        events_to_compact: list[Event] = []
        for session_event in session.events:
            if session_event.actions and session_event.actions.compaction:
                events_to_compact = []
                events_to_compact.append(session_event)
            else:
                events_to_compact.append(session_event)
        input_tokens: int = 0
        output_tokens: int = 0

        for event in events_to_compact:
            if event and event.content and event.content.parts:
                usage = event.usage_metadata
                if usage:
                    if usage.prompt_token_count:
                        input_tokens += usage.prompt_token_count
                    if usage.candidates_token_count:
                        output_tokens += usage.candidates_token_count
        total_tokens = input_tokens + output_tokens
        logger.info(
            f"Compaction check: input_tokens={input_tokens}, output_tokens={output_tokens}, total={total_tokens}"
        )
        return total_tokens > self.max_token_length

    async def run_async(  # type: ignore[no-untyped-def]
        self,
        *,
        user_id: str,
        session_id: str,
        invocation_id: str | None = None,
        new_message: Union["Content", None] = None,
        state_delta: dict[str, Any] | None = None,
        run_config: Union["RunConfig", None] = None,
    ):
        """Wraps original run_async to insert and restart runner on compaction triggers"""

        self.session_id = session_id
        self.user_id = user_id

        while True:
            generator = self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
                state_delta=state_delta,
                run_config=run_config,
            )
            logger.info("Started runner")
            async for item in generator:
                yield item
                should_compact = await self.should_compact()
                if should_compact:
                    logger.info("Compaction triggered, will exit current runner, compact events and start again")
                    new_message = Content(
                        role="user",
                        parts=[Part(text="Please continue from where you left off")],
                    )
                    break
            await generator.aclose()
            session = await self.session_service.get_session(
                app_name=self.app_name,
                session_id=session_id,
                user_id=user_id,
            )
            if session is None:
                logger.error(f"Session with ID {session_id} not found for compaction.")
                raise ValueError(f"Session with ID {session_id} not found for compaction.")
            compaction_event = await self.commpact_events(session=session)
            await self.session_service.append_event(session=session, event=compaction_event)

    async def commpact_events(self, session: "Session") -> "Event":
        events = session.events
        # Run the process-based summary generation in a thread to avoid blocking the event loop
        # The actual LLM call happens in a completely separate process
        summary_content = await to_thread(self._run_get_summary_in_process, events)
        logger.info(f"Generated compaction: {summary_content}")
        start_timestamp = events[0].timestamp
        end_timestamp = events[-1].timestamp
        event_actions = EventActions(
            compaction=EventCompaction(
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                compacted_content=Content(role="assistant", parts=[Part(text=summary_content)]),
            )
        )
        return Event(
            author="user",
            actions=event_actions,
            invocation_id=Event.new_id(),
        )

    def _run_get_summary_in_process(self, events: list["Event"], timeout: float | None = 60.0) -> str:
        """
        Run summary generation in a completely separate process.

        This method:
        1. Extracts conversation history from events (in main process)
        2. Spawns a child process to generate the summary
        3. Returns the generated summary string

        Note: Uses 'spawn' context to create a fresh Python interpreter,
        ensuring no context variables are inherited from the parent process.

        Args:
            events: List of ADK Event objects to summarize
            timeout: Maximum time in seconds to wait for the process (default: 60s)

        Returns:
            The generated summary string, or empty string on failure
        """
        # Extract conversation history in main process (before sending to subprocess)
        conversation_history = _extract_conversation_history(events)
        prompt = self.prompt_template + "\n\n" + conversation_history

        # Build model configuration dict for subprocess
        # This extracts the necessary config from LiteLlm or uses string model directly
        model_config: dict[str, Any] = {
            "app_name": self.app_name,
        }

        if isinstance(self.model, str):
            model_config["model"] = self.model
        else:
            # Extract config from LiteLlm or BaseLlm object
            # LiteLlm stores model name in .model and additional args (api_base, api_key, etc.) in ._additional_args
            model_config["model"] = getattr(self.model, "model", str(self.model))
            additional_args = getattr(self.model, "_additional_args", {}) or {}
            model_config["api_base"] = additional_args.get("api_base")
            model_config["api_key"] = additional_args.get("api_key")

        # Use spawn context for clean process isolation
        ctx = multiprocessing.get_context("spawn")

        # Create a process with a queue for returning results
        result_queue: multiprocessing.Queue[str] = ctx.Queue()

        process = ctx.Process(
            target=_process_target,
            args=(prompt, model_config, result_queue),
        )

        try:
            process.start()

            # Wait for result with timeout
            result = result_queue.get(timeout=timeout)
            process.join(timeout=5.0)  # Give process time to clean up

            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)

            return result

        except QueueEmpty:
            logger.error(f"Timeout waiting for summary generation process after {timeout}s")
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
            return ""

        except Exception:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
            return ""

    # Keep the old method as an alias for backward compatibility
    def _run_get_summary_in_thread(self, events: list["Event"]) -> str:
        """
        Backward-compatible alias for _run_get_summary_in_process.

        DEPRECATED: Use _run_get_summary_in_process instead.
        """
        return self._run_get_summary_in_process(events)
