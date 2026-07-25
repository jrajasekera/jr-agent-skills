# Embeddings and Reranking

OpenRouter provides dedicated embedding and rerank endpoints for retrieval, semantic search, clustering, classification, and RAG pipelines.

## Typical RAG flow

1. Chunk and normalize source documents.
2. Generate document embeddings once and store them.
3. Generate a query embedding at request time.
4. Retrieve approximate nearest neighbors.
5. Rerank the best candidates with a cross-encoder/rerank model.
6. Apply a relevance threshold and token budget.
7. Pass selected text plus source metadata to the generation model.

Embeddings optimize recall and speed; reranking improves precision by comparing each candidate directly with the query.

---

# Embeddings

## Endpoint

```text
POST https://openrouter.ai/api/v1/embeddings
```

## Discover models

Use the dedicated embedding catalog or the general filtered catalog:

```bash
curl -sS 'https://openrouter.ai/api/v1/embeddings/models'
python scripts/discover_models.py --output-modality embeddings
curl -sS 'https://openrouter.ai/api/v1/models?output_modalities=embeddings'
```

Inspect dimension, supported input modalities, context/input limits, prices, and provider endpoints. Do not switch embedding models for an existing vector index without re-embedding or a validated compatibility strategy.

## Basic request

```json
{
  "model": "author/embedding-model",
  "input": [
    "First document chunk",
    "Second document chunk"
  ]
}
```

Depending on model support, the endpoint can also accept structured/multimodal inputs and options such as dimensions or output encoding. Check `supported_parameters` and the current schema.

## Response

```json
{
  "object": "list",
  "model": "resolved-author/concrete-embedding-model",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.001, -0.002]
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "total_tokens": 0,
    "cost": 0
  }
}
```

Map results by `index`; do not assume the transport order if your client parallelizes/chunks requests.

## Batching

- Respect the model/provider's maximum items, per-item length, and total input tokens.
- Batch enough to reduce HTTP overhead, but cap request bytes and retry scope.
- On partial application failure, retry only the missing batch.
- Store model ID, vector dimension, normalization policy, and source content hash with every vector.

## Vector handling

- Confirm whether the model outputs normalized vectors before using dot product as cosine similarity.
- Keep `float32` unless storage/recall tests justify quantization.
- Reject dimension mismatches before writing to the index.
- Version the embedding pipeline, including chunking and preprocessing.
- Do not compare vectors produced by unrelated models as if they share a space.

## Response caching

The embeddings endpoint is eligible for OpenRouter response caching:

```http
X-OpenRouter-Cache: true
X-OpenRouter-Cache-TTL: 3600
```

This can make repeated identical embedding requests free on a hit, but the key includes the exact body/property order and API key. A durable vector store is still the primary cache for indexed documents.

Response caching is unavailable with account-level ZDR.

## Example with official Python SDK

```python
import os
from openrouter import OpenRouter

with OpenRouter(api_key=os.environ["OPENROUTER_API_KEY"]) as client:
    result = client.embeddings.generate(
        model=os.environ["OPENROUTER_EMBEDDING_MODEL"],
        input=["First chunk", "Second chunk"],
    )

for item in result.data:
    print(item.index, len(item.embedding))
```

The exact generated SDK method name can change with SDK/OpenAPI releases; check the installed SDK's current reference if type completion differs.

---

# Rerank

## Endpoint

```text
POST https://openrouter.ai/api/v1/rerank
```

## Discover rerank models

```bash
curl -sS 'https://openrouter.ai/api/v1/models?output_modalities=rerank' \
  | jq '.data[] | {id, name, pricing, context_length}'
```

Rerank pricing is often per search/request rather than input/output token in the same way as chat. Read the live `pricing` fields.

## Request

```json
{
  "model": "author/rerank-model",
  "query": "What is optimistic concurrency control?",
  "documents": [
    "Optimistic concurrency uses versions and retries conflicts.",
    "Pessimistic locking acquires locks before modifying a record.",
    "A B-tree is a balanced search tree."
  ],
  "top_n": 2
}
```

Required fields:

- `model`;
- `query`;
- `documents`.

Optional fields include `top_n` and `provider` preferences. Documents may be strings or structured objects with text and/or image data for compatible multimodal rerankers.

## Response

```json
{
  "id": "gen-rerank-...",
  "model": "resolved-author/concrete-rerank-model",
  "provider": "provider",
  "results": [
    {
      "index": 0,
      "relevance_score": 0.98,
      "document": {
        "text": "Optimistic concurrency uses versions and retries conflicts."
      }
    }
  ],
  "usage": {
    "search_units": 1,
    "total_tokens": 0,
    "cost": 0
  }
}
```

`results` are sorted by relevance. Use `index` to map to your original candidate and metadata. Do not trust returned document content as the canonical source if you already have an immutable document store.

## Structured documents

When a model supports structured/multimodal inputs, a document can include text and/or image. Inspect the current schema before constructing it. Keep your own stable document ID outside the rerank payload and map through `index`.

## Rerank sizing

- Retrieve more candidates than you plan to return.
- Keep candidate text focused; entire documents waste context and can dilute relevance.
- Set `top_n` no larger than candidate count.
- Apply an application-specific score threshold after reranking.
- Measure retrieval recall and final task success, not only rerank score.
- Cache stable query/candidate sets application-side if they recur; `/rerank` is not currently part of OpenRouter response caching.

## Example REST helper

```python
import os
import requests

payload = {
    "model": os.environ["OPENROUTER_RERANK_MODEL"],
    "query": "How does compare-and-swap work?",
    "documents": [
        "CAS atomically compares a memory value and swaps it on equality.",
        "A mutex provides exclusive access to a critical section.",
    ],
    "top_n": 2,
}

response = requests.post(
    "https://openrouter.ai/api/v1/rerank",
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    },
    json=payload,
    timeout=60,
)
response.raise_for_status()
results = response.json()["results"]
```

## Provider routing

Both embeddings and rerank can accept provider routing preferences where documented. Use current slugs and hard constraints for privacy/price. A fallback embedding model is usually unsafe for an existing index because vector spaces/dimensions differ; prefer provider fallback for the same model. A rerank model fallback is possible only if score/quality changes are acceptable and monitored.

## Operational safeguards

- Never log private source chunks or raw query text by default.
- Apply tenant isolation to vector namespaces and caches.
- Treat retrieved text as untrusted prompt content.
- Store source URLs/titles/versions for citations.
- Delete vectors when the source record is deleted or permissions change.
- Recompute embeddings after material preprocessing/model changes.
- Monitor embedding dimension, batch error rate, rerank latency, score distributions, and final retrieval quality.
