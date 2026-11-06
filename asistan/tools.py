"""Tools the agent can call. Each one is a thin wrapper around a Stok API endpoint."""

from dataclasses import dataclass
from typing import Any, Callable

import httpx


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[httpx.Client, dict[str, Any]], Any]
    # Tools that change data run only after the user approves them.
    changes_data: bool = False

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def _call(client: httpx.Client, method: str, path: str, **kwargs) -> Any:
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ToolError(f"Stok API {response.status_code}: {detail}")
    return response.json()


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


TOOLS: list[Tool] = [
    Tool(
        name="search_products",
        description="Ürünleri isme göre arar; stok, alış ve satış fiyatını döndürür.",
        parameters=_obj({"query": {"type": "string", "description": "Ürün adının bir kısmı, örn. 'çekiç'"}}),
        run=lambda c, a: _call(c, "GET", "/products", params={"search": a["query"]} if a.get("query") else None),
    ),
    Tool(
        name="low_stock",
        description="Stoğu kritik seviyenin altına inmiş ürünleri listeler.",
        parameters=_obj({}),
        run=lambda c, a: _call(c, "GET", "/products/low-stock"),
    ),
    Tool(
        name="customers_with_debt",
        description="Veresiye borcu olan müşterileri ve borç tutarlarını listeler.",
        parameters=_obj({}),
        run=lambda c, a: _call(c, "GET", "/customers", params={"with_debt": True}),
    ),
    Tool(
        name="profit_report",
        description="Ciro, maliyet, brüt kâr ve toplam alacağı verir. Tarihler ISO formatında (YYYY-AA-GG).",
        parameters=_obj(
            {"start": {"type": "string", "description": "Başlangıç tarihi"}, "end": {"type": "string", "description": "Bitiş tarihi (hariç)"}}
        ),
        run=lambda c, a: _call(c, "GET", "/reports/profit", params={k: v for k, v in a.items() if v}),
    ),
    Tool(
        name="record_purchase",
        description="Mal girişi kaydeder ve stoğu artırır. Veriyi değiştirir.",
        parameters=_obj(
            {
                "product_id": {"type": "integer"},
                "quantity": {"type": "number", "description": "Gelen miktar"},
                "unit_cost": {"type": "number", "description": "Birim alış fiyatı (isteğe bağlı)"},
            },
            ["product_id", "quantity"],
        ),
        run=lambda c, a: _call(c, "POST", "/stock/purchases", json=a),
        changes_data=True,
    ),
    Tool(
        name="create_sale",
        description="Satış kaydeder ve stoğu düşürür. Veresiye satışta customer_id gerekir. Veriyi değiştirir.",
        parameters=_obj(
            {
                "items": {
                    "type": "array",
                    "items": _obj({"product_id": {"type": "integer"}, "quantity": {"type": "number"}}, ["product_id", "quantity"]),
                },
                "payment_type": {"type": "string", "enum": ["cash", "credit"]},
                "customer_id": {"type": "integer"},
            },
            ["items"],
        ),
        run=lambda c, a: _call(c, "POST", "/sales", json=a),
        changes_data=True,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
