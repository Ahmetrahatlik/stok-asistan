import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from asistan.llm import ChatModel
from asistan.tools import TOOLS, TOOLS_BY_NAME, ToolError

SYSTEM_PROMPT = """Sen bir hırdavat dükkânının stok asistanısın. Türkçe, kısa ve net cevap ver.
Kurallar:
- Stok, fiyat, borç ve kâr bilgisini yalnız araçlardan al; sayı uydurma.
- Araç hata dönerse hatayı sade dille kullanıcıya söyle.
- Veriyi değiştiren işlemlerde (mal girişi, satış) aracı çağır; sistem kullanıcıdan onay alacak.
- Ürün kimliğini bilmiyorsan önce search_products ile bul.
- Tutarları TL olarak yaz."""


@dataclass
class PendingAction:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    tool_call_id: str

    def describe(self) -> str:
        return f"{self.tool_name} {json.dumps(self.arguments, ensure_ascii=False)}"


@dataclass
class AgentReply:
    text: str | None
    pending: PendingAction | None = None
    tool_log: list[str] = field(default_factory=list)


class Agent:
    """Tool-calling loop: model -> tools -> model, stopping for approval before any write."""

    def __init__(self, model: ChatModel, stok_api: httpx.Client, max_steps: int = 6):
        self.model = model
        self.stok_api = stok_api
        self.max_steps = max_steps
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.pending: PendingAction | None = None
        self._specs = [tool.spec() for tool in TOOLS]

    def ask(self, text: str) -> AgentReply:
        if self.pending is not None:
            return AgentReply(text=f"Önce bekleyen işlemi onaylayın veya reddedin: {self.pending.describe()}", pending=self.pending)
        self.messages.append({"role": "user", "content": text})
        return self._loop()

    def resolve(self, approve: bool) -> AgentReply:
        if self.pending is None:
            return AgentReply(text="Bekleyen bir işlem yok.")
        action, self.pending = self.pending, None
        if approve:
            result = self._execute(action.tool_name, action.arguments)
            log = [f"{action.tool_name} (onaylandı)"]
        else:
            result = {"error": "Kullanıcı bu işlemi reddetti; işlem yapılmadı."}
            log = [f"{action.tool_name} (reddedildi)"]
        self._add_tool_result(action.tool_call_id, result)
        reply = self._loop()
        reply.tool_log = log + reply.tool_log
        return reply

    def _loop(self) -> AgentReply:
        log: list[str] = []
        for _ in range(self.max_steps):
            message = self.model.complete(self.messages, self._specs)
            self.messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                return AgentReply(text=message.get("content") or "", tool_log=log)

            for index, call in enumerate(calls):
                name = call["function"]["name"]
                arguments = _parse_arguments(call["function"].get("arguments"))
                tool = TOOLS_BY_NAME.get(name)
                if tool is not None and tool.changes_data:
                    # Every call in this message needs a result before the model runs again,
                    # so later calls are skipped and the model can repeat them after approval.
                    for skipped in calls[index + 1 :]:
                        self._add_tool_result(skipped["id"], {"error": "Önceki işlem onay bekliyor; bu çağrı yapılmadı."})
                    self.pending = PendingAction(uuid.uuid4().hex[:8], name, arguments, call["id"])
                    return AgentReply(text=None, pending=self.pending, tool_log=log)
                result = self._execute(name, arguments)
                log.append(name)
                self._add_tool_result(call["id"], result)
        return AgentReply(text="İşlem çok fazla adım sürdü, lütfen soruyu daraltın.", tool_log=log)

    def _execute(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            return {"error": f"Bilinmeyen araç: {name}"}
        try:
            return tool.run(self.stok_api, arguments)
        except ToolError as exc:
            return {"error": str(exc)}
        except httpx.HTTPError as exc:
            return {"error": f"Stok API'ye ulaşılamadı: {exc}"}

    def _add_tool_result(self, call_id: str, result: Any) -> None:
        self.messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False, default=str)})


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
