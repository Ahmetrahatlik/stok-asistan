"""Terminal chat: python -m asistan.cli"""

from asistan.agent import Agent
from asistan.config import settings
from asistan.llm import OpenAICompatibleModel
from asistan.stok_client import make_stok_client


def main() -> None:
    agent = Agent(
        OpenAICompatibleModel(settings.llm_base_url, settings.llm_api_key, settings.llm_model),
        make_stok_client(settings),
        settings.max_steps,
    )
    print("Stok Asistanı. Çıkmak için boş satır girin.")
    while True:
        text = input("\nSiz: ").strip()
        if not text:
            break
        reply = agent.ask(text)
        while reply.pending:
            answer = input(f"Onay gerekiyor -> {reply.pending.describe()} [e/h]: ").strip().lower()
            reply = agent.resolve(answer.startswith("e"))
        if reply.tool_log:
            print(f"(kullanılan araçlar: {', '.join(reply.tool_log)})")
        print(f"Asistan: {reply.text}")


if __name__ == "__main__":
    main()
