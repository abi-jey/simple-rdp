from google.adk import Runner
from google.adk.agents import Agent
from google.adk.sessions import Session
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.genai.types import Content
from google.genai.types import Part

root_agent = Agent(
    name="search_assistant",
    model="gemini-2.5-flash",  # Or your preferred Gemini model
    instruction="You are a helpful assistant. Answer user questions using Google Search when needed.",
    description="An assistant that can search the web.",
    tools=[],
)

session_service = DatabaseSessionService(db_url="sqlite+aiosqlite:///./adk_agent_data.db")


async def get_session(session_id: str | None = None) -> Session:
    if session_id is None:
        print("No session ID provided. Creating a new session...")
        session = await session_service.create_session(app_name="adk-agent", user_id="user123")
        print(f"Created new session with ID: {session.id}")
        return session
    print(f"Retrieving session with ID: {session_id}...")
    session = await session_service.get_session(app_name="adk-agent", session_id=session_id, user_id="user123")
    if session:
        print(f"Session found: {session.id}")
        return session
    raise ValueError(f"Session with ID {session_id} not found")


async def main(q: str, session_id: str | None = None):
    runner = Runner(
        agent=root_agent,
        session_service=DatabaseSessionService(db_url="sqlite+aiosqlite:///./adk_agent_data.db"),
        app_name="adk-agent",
    )
    question = "What is the capital of France?"

    session = await get_session(session_id=session_id)
    runner = runner.run_async(
        user_id="user123",
        session_id=session.id,
        new_message=Content(
            role="user",
            parts=[Part(text=question)],
        ),
    )
    async for response in runner:
        print(f"Received response part: {response}")
    # print(f"Q: {question}\nA: {response}")


if __name__ == "__main__":
    # Example usage
    question = "What is the capital of France?"
    session_id = None  # Or set to an existing session ID to continue a conversation
    import asyncio

    asyncio.run(main(question, session_id))
