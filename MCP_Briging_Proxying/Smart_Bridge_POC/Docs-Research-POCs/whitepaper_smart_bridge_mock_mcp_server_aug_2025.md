# Whitepaper — Smart Bridge & Mock MCP Server
*Date: 20 Aug 2025*

## Executive summary
This paper distills practical lessons from popular open‑source MCP servers and lays out a blueprint for a **Smart Bridge** and a **Mock MCP Server** suite. Had this suite existed months earlier, teams shipping MCP servers and clients would have saved significant time on:
- multi‑transport support (stdio ⇄ Streamable HTTP/SSE/WS),
- robust framing/correlation under load,
- testable redaction/sanitization,
- record/replay debugging, and
- client conformance testing via a scripted faux server.

We also outline how MCP parties can operate **mutually as clients and servers** in collaborative, horizontal topologies—what we call **peer MCP**—and what additional guardrails are needed (loop prevention, routing, and cancellation semantics) to make that safe in practice.

---

## Part I — What we learned from the field
Below is a synthesis of behaviors commonly seen across rich MCP servers (e.g., code‑hosting, web‑scraping, filesystem/reference servers) and why those behaviors matter when designing bridges, mocks, and tests.

### 1) Transports are a moving target
- **stdio** is ideal for single‑client, low‑latency local use. It is sensitive to framing bugs and stdout/stderr mixing.
- **Streamable HTTP** generalizes remote connectivity; **SSE** is often used for server→client streaming; **WebSocket** appears when bidirectional interactivity is desired from the browser.
- Servers that support more than one transport gain adoption but carry risk: inconsistent behavior across transports becomes a common source of bugs.

**Implication:** a bridge that normalizes transports and offers golden‑trace parity checks (same request over different transports → byte‑identical semantic result) becomes invaluable.

### 2) Streaming is table‑stakes for UX
- Long‑running tools (crawl, search, indexing, CI) need progress updates, partial results, and cancellations.
- Notification traffic (logs, heartbeats) increases the chance of back‑pressure and ordering issues.

**Implication:** bridges and clients must treat streaming as the norm, not the exception; mocks should simulate partials, retries, and cancellations reliably.

### 3) Tool surfaces are large and heterogenous
- Real servers expose dozens of tools: read/write resources, code review, search, scraping, metrics, etc.
- Error shapes vary (permission, rate‑limit, validation) and must be reflected as clean JSON‑RPC errors.

**Implication:** a mock server should be scenario‑driven, not code‑path‑driven: a DSL can stage success, partials, and failures with time and size parameters.

### 4) Observability, privacy, and reproducibility matter
- Developers need structured logs, metrics, and secure redaction.
- Record/replay (“golden traces”) accelerates regression testing and client conformance.

**Implication:** bridges should ship with pluggable filters (redact/enrich/block), persistent transcript capture, and one‑command replay.

---

## Part II — Smart Bridge: reference design
The Smart Bridge is a single process that launches or connects to an MCP server and exposes it simultaneously over **HTTP POST**, **SSE**, and **WebSocket**, while accepting **stdio** as the upstream or downstream side.

### Core responsibilities
1. **Framing & correlation**
   - Strict `Content-Length` framing for stdio; canonical JSON serialization with UTF‑8.
   - `id`→session map for demux; notifications broadcast.
2. **Transport normalization**
   - Downstream: HTTP (request/response), SSE (server→client), WebSocket (bi‑di events).
   - Upstream: stdio or HTTP/WS as needed; hot‑swappable.
3. **Pluggable filter chain**
   - Hooks: `client_to_server`, `server_to_client`.
   - Actions: redact, enrich (e.g., `bridge_meta` traces), block/drop, transform.
   - Runtime toggles and per‑session scoping.
4. **Resilience**
   - Heartbeats and keep‑alives (SSE comments / WS pings).
   - Back‑pressure queues with drop policies.
   - Child supervision and graceful restarts.
5. **Observability**
   - Structured stderr logs; optional request/response sampling.
   - Golden‑trace recorder and determinstic replayer.

### Minimum viable API (downstream)
- `POST /sessions` → `{ session }`
- `GET /events?session=` → SSE stream (keep‑alive every 15s)
- `WS  /ws?session=` → bi‑di JSON frames
- `POST /messages?session=` → JSON‑RPC payload; `id` auto‑assigned if missing
- `GET /filters` / `POST /filters/{name}` → runtime filter control
- `GET /live` → streaming HTML console for demos
- `/health`, `/metrics` (optional Prometheus)

### Test hooks
- Fault injection flags per session: delay, jitter, drop %, truncate‑frame, duplicate‑frame.
- Size/latency budgets per method to simulate real servers.

---

## Part III — Mock MCP Server: design for client testing
A deterministic faux server that exercises clients by **scenario**, not internal logic.

### Scenario DSL (YAML or JSON)
```yaml
name: "streaming-cancel"
given:
  capabilities: { prompts: true, tools: true }
  tools:
    - name: crawl
      inputSchema: { type: object, properties: { url: {type: string} } }
when:
  - on: { method: "tools/call", tool: "crawl" }
    do:
      - send: { type: "progress", percent: 10 }
      - wait: 1.0
      - send: { type: "progress", percent: 55 }
      - wait: 2.0
      - ifCancelled: { send: { error: { code: "Cancelled", message: "User cancelled" } }, stop: true }
      - send: { result: { summary: "Done", items: 123 } }
```

### Built‑in behaviors
- **Handshake matrix**: missing/extra capabilities; huge tool lists; unknown tool names.
- **Streaming**: partials, progress, logs; interleaved notifications.
- **Errors**: permission, rate‑limit, validation, internal.
- **Cancellation**: respect client‑initiated cancel; emit partials.
- **Chaos**: truncated frames, resets, reordering.

### Control plane (OpenAPI)
- Start/stop scenario; advance step; inject fault; fetch transcript; toggle filters.

### Outputs
- Golden transcripts: canonicalized JSON with timing annotations.
- Client conformance report: pass/fail per scenario, screenshots (optional), and diffs vs golden.

---

## Part IV — If the suite existed earlier: concrete benefits
1. **Transport correctness out‑of‑the‑box**
   - New servers could launch with stdio + Streamable HTTP (+SSE/WS) on day one.
2. **Faster client integration**
   - Client teams could test against the Mock MCP Server’s scenarios without standing up real backends.
3. **Safer logs & privacy**
   - Redaction filters prevent accidental token exfiltration during demos and CI.
4. **Reproducible bugs**
   - Golden‑trace replays make flaky transport issues debuggable and shareable.
5. **Performance envelopes**
   - Synthetic load + streaming simulation provide early p95/p99 estimates before hitting real APIs.

---

## Part V — Collaborative MCP (peers, not hierarchy)
Yes: MCP parties can operate **mutually as clients and servers**. The protocol does not forbid it; you can build a **horizontal, collaborative mesh** where each node both exposes tools and consumes others’ tools. To make this safe and predictable, add the following conventions at the application layer:

### 1) Topologies
- **Hub‑and‑spoke**: a coordinator node mediates; simpler auth and routing.
- **Mesh**: peers connect directly; better resilience; more complex routing.
- **Daisy‑chain / ring**: useful for staged processing pipelines.

### 2) Routing & loop prevention
- Attach a `bridge_meta` (or similar) to every outbound request:
  - `trace_id`, `span_id`, `parent_id`
  - `hops` (TTL), decrement at each forward
  - `route` (list of node IDs visited)
- Drop or short‑circuit if `hops == 0` or `self` appears in `route`.

### 3) Concurrency & cancellation
- Propagate cancellation downstream with deadlines.
- Enforce per‑route concurrency caps and budgets (CPU, I/O, tool invocations).

### 4) Identity & ACLs
- Issue **peer credentials** distinct from user credentials; attach per‑tool scopes.
- Maintain **allow/deny lists** at the filter layer for high‑risk tools.

### 5) Failure semantics
- Prefer **idempotent retries** with dedupe keys.
- Use **circuit breakers**: open on N consecutive failures; back‑off; emit peer‑health notifications.

**Smart Bridge role:** the bridge already has filter hooks, correlation, and multi‑transport fan‑out—perfect to implement peer routing, loop guards, and per‑peer budgets without modifying server code.

---

## Part VI — Phased roadmap
**Phase 1 — Ship the Smart Bridge (foundation)**
- Harden framing, demux, back‑pressure; add `/metrics` and recorder/replayer.
- Build test matrix (transport, protocol, filters, faults, soak, golden).

**Phase 2 — Mock MCP Server (client conformance)**
- Implement the Scenario DSL + control plane; publish baseline scenario packs.
- CI integration: run against popular clients; publish badges.

**Phase 3 — Peer MCP (collaborative mesh)**
- Add routing metadata, hop TTL, and loop guards to the bridge.
- Publish sample pipelines (e.g., Crawl → Summarize → Index → Verify) across two or more nodes.

**Phase 4 — Ecosystem adapters**
- Plugins for auth providers, tracing backends (OTel), and storage for transcripts.

---

## Part VII — Test matrix (ready to paste into CI)
- **Transport/framing**: header anomalies, partial frames, SSE reconnects, WS slow consumer, child restarts.
- **Protocol**: `id` correlation, notifications broadcast, batch/ordering, error taxonomy, cancellation windows.
- **Filters**: redaction true/false positives, drop semantics, ordering, perf budget.
- **Faults/soak**: half‑open sockets, TLS proxy timeouts, malformed JSON, deep nesting, hour‑long soak with rotating clients.
- **Golden parity**: same request across transports → equal semantic result; replay stable across versions.

---

## Appendix A — Minimal filter cookbook
- **Redact secrets**: regex scan strings → replace with `[REDACTED]`.
- **Annotate traces**: add `bridge_meta` with trace IDs, hop count.
- **Blocklists/allowlists**: drop high‑risk methods per peer/session.
- **Shaping**: inject delays/jitter to mimic real backends.

## Appendix B — Scenario snippets
- **Permission error**: first call returns 403‑like error; second (with token) succeeds.
- **Streaming + cancel**: emit progress/logs; cancel at 60%; return partial summary.
- **Rate limit**: respond with `retry_after`; client should back‑off, not spam.

## Appendix C — Operational tips
- Keep protocol on `stdout` only; **all logs to `stderr`**.
- Never block the event loop; offload CPU to workers.
- Bound concurrent tool calls; prefer streaming outputs.
- Use **golden traces** to freeze behavior before refactors.

---

*Prepared for the MCP_Testing_Tools project to guide design, testing, and collaboration across bridges, mocks, and real servers.*

