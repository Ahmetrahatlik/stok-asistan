# Stok Asistanı

[Stok API](https://github.com/Ahmetrahatlik/stok-api) için Türkçe konuşan bir yapay zekâ ajanı. Dükkân sahibi "Çekiçten kaç tane kaldı?", "Bu ay kâr ne?", "Mehmet Usta'ya 3 çekiç veresiye yaz" gibi cümleler yazar; ajan doğru API uçlarını araç (tool-calling) olarak çağırır ve cevabı gerçek veriden verir.

*A Turkish-speaking tool-calling agent for the Stok API. Read questions are answered from live data; anything that changes data waits for human approval. English summary below.*

![CI](https://github.com/Ahmetrahatlik/stok-asistan/actions/workflows/ci.yml/badge.svg)

## Nasıl çalışıyor?

```
Kullanıcı ──> Ajan ──> LLM (OpenAI uyumlu API)
               │          │ tool_calls
               │ <────────┘
               ├─ okuma aracı  ──> Stok API ──> sonuç modele geri döner
               └─ yazma aracı  ──> DURUR, kullanıcıdan onay ister
                                     ├─ onay  ──> Stok API'ye gönderilir
                                     └─ red   ──> hiçbir şey değişmez
```

- **Araçlar:** ürün arama, kritik stok, borçlu müşteriler, kâr raporu (okuma); mal girişi, satış (yazma).
- **İnsan onayı:** Veriyi değiştiren araçlar onay gelmeden çalışmaz. Onay beklenirken yeni soru kabul edilmez.
- **Sağlam döngü:** Bilinmeyen araç, bozuk JSON argüman, API hatası (ör. yetersiz stok 409) veya API'ye ulaşılamaması modele hata olarak geri verilir; ajan çökmez. Sonsuz araç döngüsüne karşı adım sınırı var.
- **Model bağımsız:** OpenAI uyumlu her sunucuyla çalışır: Ollama, LM Studio, OpenAI, Gemini. Ayar ortam değişkenleriyle yapılır.

## Önemli kararlar

- **Neden onay?** Model yanlış ürünü ya da miktarı seçebilir. Okuma hatası zararsızdır, ama yanlış bir satış stoğu ve müşteri borcunu bozar. Bu yüzden karar her zaman insanda kalır.
- **Aynı mesajda birden çok araç:** Model bir mesajda hem okuma hem yazma aracı isterse okumalar çalışır, yazma onaya düşer, sonraki çağrılara "onay bekliyor" sonucu yazılır. Böylece her araç çağrısı bir cevap alır ve sohbet geçmişi modele geçerli kalır.
- **Testler gerçek LLM'e bağlı değil:** Testlerde senaryolu sahte bir model ve bellekte çalışan sahte bir Stok API kullanılıyor. Ajan davranışı (onay, red, hata, adım sınırı) her seferinde aynı sonucu veriyor ve CI'da ücretsiz koşuyor.
- **Gerçek entegrasyonda bulunan hata:** Ajanı gerçek Stok API'ye bağlayınca "çek" araması "Çekiç"i bulamadı; SQL'in büyük/küçük harf eşleştirmesi Türkçe harflerde çalışmıyordu. Hata Stok API'de düzeltildi.

## Çalıştırma

1. Stok API'yi çalıştırın (`docker compose up` ile, [Stok API](https://github.com/Ahmetrahatlik/stok-api) README'sine bakın).
2. Bir model seçin. Örneğin yerelde Ollama ile:

```bash
ollama pull qwen2.5:7b
```

3. Asistanı başlatın:

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Terminalden sohbet
python -m asistan.cli

# ya da HTTP API (http://localhost:8001/docs)
uvicorn asistan.api:app --port 8001
```

Ortam değişkenleri:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI uyumlu uç (Ollama) |
| `LLM_API_KEY` | `ollama` | Bulut sağlayıcıda gerçek anahtar |
| `LLM_MODEL` | `qwen2.5:7b` | Araç çağırabilen bir model |
| `STOK_API_URL` | `http://localhost:8000` | Stok API adresi |
| `AGENT_MAX_STEPS` | `6` | Bir soruda en fazla model turu |

HTTP API: `POST /chat` `{"message": "...", "session_id": "..."}` cevabında `pending_action` doluysa `POST /chat/{session_id}/decision` `{"approve": true}` ile onaylanır.

## Testler

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Proje yapısı

```
asistan/
  agent.py    araç döngüsü ve onay mantığı
  tools.py    araç tanımları (JSON şema) ve Stok API çağrıları
  llm.py      OpenAI uyumlu model istemcisi
  api.py      FastAPI uçları (/chat, /decision)
  cli.py      terminal sohbeti
tests/        sahte model ve sahte Stok API ile testler
```

## Geliştirme süreci

Proje, Claude Code ile yapay zekâ destekli geliştirildi. Araçları, onay kuralını ve kabul kriterlerini ben belirledim, kod ajanla yazıldı, davranışlar otomatik testlerle ve gerçek Stok API'ye karşı denenerek doğrulandı.

---

## English summary

- Turkish natural-language agent over the Stok API using OpenAI-style **tool calling**; works with Ollama, LM Studio, OpenAI or Gemini via an OpenAI-compatible endpoint.
- **Human-in-the-loop:** read tools run immediately; write tools (purchases, sales) pause until the user approves or rejects.
- **Robust loop:** unknown tools, malformed arguments, API errors and unreachable services are returned to the model as errors; a step limit stops runaway loops.
- **Deterministic tests:** a scripted fake model and an in-memory fake Stok API, so CI needs no LLM key.
- Integration testing against the real API surfaced a Turkish case-folding search bug, fixed upstream in Stok API.
