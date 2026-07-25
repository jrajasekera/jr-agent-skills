# Tool Calling and Server Tools

OpenRouter supports three distinct extension mechanisms. Choosing the wrong one is a common source of broken agent loops and unsafe side effects.

| Mechanism | Declared in | Who executes it? | Invocation count |
|---|---|---|---|
| User-defined function tool | `tools` | Your application | Model may request 0-N calls |
| OpenRouter server tool | `tools` with `openrouter:*` type | OpenRouter, except human-in-loop outputs such as patches | Model may request 0-N calls |
| Plugin | `plugins` | OpenRouter pipeline | Runs once when enabled/needed |

## User-defined function tools

A function tool describes a capability; it does not expose an implementation to the model.

### Chat Completions shape

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {
          "type": "object",
          "properties": {
            "city": { "type": "string" },
            "units": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"]
            }
          },
          "required": ["city"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "provider": {
    "require_parameters": true
  }
}
```

### Responses shape

Responses uses a flat function definition:

```json
{
  "tools": [
    {
      "type": "function",
      "name": "get_weather",
      "description": "Get current weather for a city.",
      "parameters": {
        "type": "object",
        "properties": {
          "city": { "type": "string" }
        },
        "required": ["city"],
        "additionalProperties": false
      },
      "strict": true
    }
  ]
}
```

Do not copy one shape into the other endpoint.

## Tool-choice controls

Current common controls include:

```json
{ "tool_choice": "auto" }
{ "tool_choice": "none" }
{ "tool_choice": "required" }
```

To force a named function in Chat Completions:

```json
{
  "tool_choice": {
    "type": "function",
    "function": { "name": "get_weather" }
  }
}
```

Responses uses its own tool-choice object. Inspect the current schema rather than translating the Chat object verbatim.

`parallel_tool_calls: true` allows the model to request several calls in one turn. Your application must return one result for every call ID, including failures.

## The safe Chat Completions loop

1. Send conversation plus tool definitions.
2. Append the assistant message exactly as returned.
3. Validate every tool name and argument object against a local allowlist/schema.
4. Authorize the operation for the current user/tenant.
5. Execute with timeout, output-size, network, and side-effect limits.
6. Append one `role: "tool"` result for each `tool_call_id`.
7. Preserve `reasoning_details` exactly on the assistant message.
8. Call the model again.
9. Stop on a final response or a configured step/cost/time limit.

### Bounded TypeScript pattern

```typescript
type ChatMessage = Record<string, unknown>;

type Limits = {
  maxSteps: number;
  maxToolCalls: number;
  maxToolResultChars: number;
};

async function runAgent(
  initialMessages: ChatMessage[],
  tools: unknown[],
  limits: Limits,
): Promise<string> {
  const messages = [...initialMessages];
  let totalToolCalls = 0;

  for (let step = 0; step < limits.maxSteps; step += 1) {
    const response = await callOpenRouter({
      messages,
      tools,
      tool_choice: "auto",
      parallel_tool_calls: true,
      provider: { require_parameters: true },
    });

    const assistant = response.choices?.[0]?.message;
    if (!assistant) throw new Error("OpenRouter returned no assistant message");

    // Preserve content, tool_calls, reasoning_details, and any opaque fields.
    messages.push(assistant);

    const calls = assistant.tool_calls ?? [];
    if (calls.length === 0) return assistant.content ?? "";

    totalToolCalls += calls.length;
    if (totalToolCalls > limits.maxToolCalls) {
      throw new Error("Tool-call budget exceeded");
    }

    const results = await Promise.all(
      calls.map(async (call: any) => {
        const name = call.function?.name;
        const rawArguments = call.function?.arguments ?? "{}";
        const parsed = JSON.parse(rawArguments);

        // validateAndAuthorize must reject unknown tools/fields and enforce
        // tenant/user permissions before executeTool performs side effects.
        const args = validateAndAuthorize(name, parsed);
        const value = await executeToolWithTimeout(name, args, 15_000);
        const serialized = JSON.stringify(value);

        if (serialized.length > limits.maxToolResultChars) {
          throw new Error(`Tool result too large: ${name}`);
        }

        return {
          role: "tool",
          tool_call_id: call.id,
          content: serialized,
        };
      }),
    );

    messages.push(...results);
  }

  throw new Error("Agent step limit exceeded");
}
```

Production code must also bound total elapsed time, model cost/tokens, retries, and concurrent side effects.

## Tool result errors

A tool execution failure should usually be returned as a concise structured result so the model can recover:

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "{\"ok\":false,\"error\":{\"type\":\"timeout\",\"message\":\"Weather service timed out\"}}"
}
```

Do not expose stack traces, credentials, internal hostnames, SQL, or unrelated user data. If retrying the tool is unsafe, say so in the result.

## Preserving reasoning state

Reasoning models can return `reasoning_details` containing plaintext, summaries, encrypted data, signatures, and provider-specific formats. During a tool loop:

- preserve the entire array;
- preserve order and consecutive blocks;
- do not strip fields that look opaque;
- do not merge blocks from different responses;
- do not fabricate reasoning for a reconstructed assistant message.

The assistant tool-call message should be stored and replayed as a whole. This is especially important when a model pauses an extended-thinking response to request a tool.

## Streaming tool calls

Chat Completions streams tool calls as indexed deltas. Accumulate each field by index:

```typescript
const calls = new Map<number, {
  id?: string;
  type?: string;
  function: { name: string; arguments: string };
}>();

function applyToolDelta(delta: any): void {
  for (const part of delta.tool_calls ?? []) {
    const current = calls.get(part.index) ?? {
      function: { name: "", arguments: "" },
    };

    if (part.id) current.id = part.id;
    if (part.type) current.type = part.type;
    if (part.function?.name) current.function.name += part.function.name;
    if (part.function?.arguments) {
      current.function.arguments += part.function.arguments;
    }

    calls.set(part.index, current);
  }
}
```

Do not parse `arguments` until the call is complete. A partial JSON string is expected while streaming.

## Responses-compatible built-in tool shapes

In addition to caller functions, the current Responses schema includes OpenAI-style built-in/provider tool shapes such as `web_search`, `file_search`, `computer_use_preview`, `code_interpreter`, `mcp`, `image_generation`, `local_shell`, `shell`, `apply_patch`, `custom`, and `namespace`. They are not aliases for the `openrouter:*` tools below. Treat each as a separate, evolving contract and verify its input schema, output items, approval model, and endpoint/provider support in the live OpenAPI.

## OpenRouter server tools

Server tools use an `openrouter:` type and can be invoked by the model during a request:

```json
{
  "tools": [
    { "type": "openrouter:web_search" },
    { "type": "openrouter:web_fetch" },
    { "type": "openrouter:datetime" }
  ]
}
```

OpenRouter's documentation currently lists tools in these families:

| Type | Purpose |
|---|---|
| `openrouter:web_search` | Search current web information |
| `openrouter:web_fetch` | Fetch and extract URL content |
| `openrouter:datetime` | Obtain current date/time context |
| `openrouter:image_generation` | Generate images during a model workflow |
| `openrouter:experimental__search_models` | Discover/select OpenRouter models |
| `openrouter:advisor` | Consult a configured advisor model |
| `openrouter:subagent` | Delegate work to a sub-agent |
| `openrouter:fusion` | Multi-model deliberation |
| `openrouter:apply_patch` | Produce a validated V4A patch for the caller to apply |
| `openrouter:shell` | Execute a constrained server-side shell workflow where supported |
| `openrouter:files` | Read, write, edit, and list workspace files; requires explicit file-tool opt-in |

Server tools are beta and surface-specific. Some are Responses-only. Always open the current tool guide and OpenAPI before using configuration fields.

The Files server tool requires the request header `x-openrouter-file-ids: openrouter`. Scope workspace access carefully, and do not assume that adding a file ID to another inference shape grants the same read/write behavior. The live OpenAPI can expose additional beta or compatibility tool types such as `openrouter:bash`; inspect their exact schemas instead of inferring behavior from the prefix.

### Bound server-tool loops

Use top-level server-tool controls where the current schema supports them:

```json
{
  "max_tool_calls": 8,
  "stop_server_tools_when": [
    { "type": "max_cost", "max_cost_in_dollars": 0.25 }
  ]
}
```

`max_tool_calls` limits outer server-tool steps. `stop_server_tools_when` supports richer stop conditions and can take precedence over a simple count according to the current beta schema. Advisor, sub-agent, and fusion tools can also expose their own nested budgets. Do not copy default/max values into production validation without checking the current tool guide.

### Server-tool safety

- Set explicit tool-call, token, cost, and elapsed-time budgets.
- Restrict nested tools offered to advisor/sub-agent workflows.
- Treat fetched web content as untrusted data, not instructions.
- Do not assume server-generated patches have been applied.
- Review and sandbox shell/patch effects.
- Preserve citations/annotations returned by search/fetch tools.
- Log which server tools ran through router metadata, but not sensitive tool payloads.

## Web search: server tool vs plugin

New agentic integrations should prefer:

```json
{
  "tools": [{ "type": "openrouter:web_search" }]
}
```

The model can choose when and how often to search. The legacy `web` plugin and `:online` suffix still run a one-shot grounding transform and may be simpler for a non-agentic request, but the plugin is deprecated in favor of the server tool.

## Apply Patch is human-in-the-loop

`openrouter:apply_patch` is a Responses-only server tool that asks a model to produce a V4A diff and has OpenRouter validate the patch syntax. OpenRouter does not write to the caller's filesystem.

A safe caller must:

1. parse the returned patch item;
2. reject absolute/traversal paths and out-of-scope files;
3. show or review the diff when policy requires it;
4. apply in a sandbox/worktree;
5. run tests/static checks;
6. return an `apply_patch_call_output` item describing success/failure.

## Plugins are not tools

Plugins run once as request/response transforms. Examples include PDF parsing, response healing, and context compression. Do not wait for a plugin `tool_call`, and do not send a tool result for one.

See [plugins-features.md](plugins-features.md).

## Tool design guidance

### Good tool schemas

- Use a single, stable action per tool.
- Write descriptions that state preconditions and side effects.
- Use enums and `additionalProperties: false`.
- Prefer IDs over free-form names after a search step.
- Separate read operations from write/delete operations.
- Return compact structured data, not entire databases or HTML pages.

### Idempotency

For mutations, accept or derive an idempotency key and persist the result. Model retries can repeat a tool call even when the previous HTTP response was lost.

### Confirmation boundaries

Require explicit human approval for destructive, financial, security-sensitive, or irreversible operations. The model's `tool_call` is a proposal, not authorization.

### Untrusted tool output

Tool results can contain prompt injection. Delimit and label them as data, minimize content, and keep system policy outside the tool result. Never grant additional tools because fetched content asks for them.

## Common mistakes

- Executing a tool name that is not in an allowlist.
- Trusting JSON arguments without schema validation.
- Returning tool results without matching `tool_call_id` / `call_id`.
- Dropping the assistant tool-call message from the next request.
- Dropping or editing `reasoning_details`.
- Parsing streamed arguments before the final delta.
- Allowing unbounded recursive server tools/sub-agents.
- Applying an `apply_patch` result without review and tests.
- Treating `:online` as equivalent to a multi-step search agent.
