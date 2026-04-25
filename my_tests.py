from langchain_core.messages import HumanMessage  # noqa: E402

from tests.agent.conftest import MockChatModel  # noqa: E402

mock_chat_model = MockChatModel(
    [
        "SELECT COUNT(*) AS n FROM students",
        "There are 20 students enrolled.",
    ]
)

messages = mock_chat_model.invoke(
    [HumanMessage(content="How many students are there?")]
)
print(messages.content)
