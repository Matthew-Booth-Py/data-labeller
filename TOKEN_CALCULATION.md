
# Token Usage Calculation

## Configuration Changes

### Before
- **Chunk Size**: 1000 chars
- **Chunk Overlap**: 200 chars
- **Concurrency**: 5 concurrent requests
- **Document Size**: ~1,951 chunks

### After
- **Chunk Size**: 4000 chars ✅
- **Chunk Overlap**: 800 chars ✅
- **Concurrency**: 2 concurrent requests ✅
- **Document Size**: ~488 chunks (75% reduction!)

---

## Token Usage Per Request

### Context Generation Request
Each contextualization request includes:

**System Prompt** (cached after first request):
```
You are a document analyst. You will be given a document excerpt to reference.

<document_excerpt>
[First 25,000 chars of document - ~6,250 tokens]
</document_excerpt>

When given a chunk, respond with ONE brief sentence...
```

**User Prompt** (per chunk):
```
Provide a short context for this chunk:

<chunk>
[4000 chars - ~1,000 tokens]
</chunk>
```

**Completion** (response):
- ~50-100 tokens (one brief sentence)

### Token Breakdown Per Request

| Component | Tokens | Cached After 1st? |
|-----------|--------|-------------------|
| System prompt (document excerpt) | ~6,250 | ✅ Yes (50% discount) |
| User prompt (chunk) | ~1,000 | ❌ No |
| Completion (response) | ~75 | ❌ No |
| **Total per request** | **~7,325** | |
| **After caching** | **~4,200** | (system prompt 50% off) |

---

## Total Token Usage

### For Your Document (488 chunks)

**First Request** (no cache):
- Input: 6,250 + 1,000 = 7,250 tokens
- Output: 75 tokens
- **Total: 7,325 tokens**

**Subsequent Requests** (with cache):
- Input: 3,125 (cached) + 1,000 = 4,125 tokens
- Output: 75 tokens
- **Total: 4,200 tokens per chunk**

**Total for Document**:
```
First request:     7,325 tokens
Next 487 requests: 487 × 4,200 = 2,045,400 tokens
─────────────────────────────────────────────
Total:             2,052,725 tokens
```

### Cost Breakdown

**Example Pricing (set by `OPENAI_MODEL`)**:
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens
- Cached input: $0.075 per 1M tokens (50% discount)

**Input Tokens**:
- Uncached: 7,250 tokens × $0.15/1M = $0.0011
- Cached: 1,522,875 tokens × $0.075/1M = $0.1142
- Uncached (chunks): 487,000 tokens × $0.15/1M = $0.0731
- **Total input: $0.1884**

**Output Tokens**:
- 488 × 75 = 36,600 tokens × $0.60/1M = $0.0220
- **Total output: $0.0220**

**Total Cost per Document**: **~$0.21**

---

## Rate Limit Analysis

### OpenAI Rate Limits (Your Tier)
- **TPM (Tokens Per Minute)**: 500,000
- **RPM (Requests Per Minute)**: Varies by tier

### With New Settings (Concurrency = 2)

**Tokens per request**: ~4,200 tokens (after cache)

**Max requests per minute**:
```
500,000 TPM ÷ 4,200 tokens/request = ~119 requests/min
```

**With concurrency = 2**:
- 2 concurrent requests = ~8,400 tokens in flight
- Well under the 500K TPM limit
- Should rarely hit rate limits!

**Time to complete 488 chunks**:
```
488 chunks ÷ 119 requests/min = ~4.1 minutes
```

**Actual time** (accounting for API latency ~500ms per request):
```
488 chunks ÷ 2 concurrent = 244 sequential batches
244 batches × 0.5s = ~122 seconds = ~2 minutes
```

---

## Comparison: Old vs New Settings

| Metric | Old (1000 chars) | New (4000 chars) | Improvement |
|--------|------------------|------------------|-------------|
| **Chunks** | 1,951 | 488 | **75% fewer** |
| **Total Tokens** | ~8.2M | ~2.05M | **75% fewer** |
| **Cost** | ~$0.84 | ~$0.21 | **75% cheaper** |
| **Time** | ~2-3 hours | ~2-5 minutes | **97% faster** |
| **Rate Limit Hits** | Constant | Rare | **Much better** |

---

## Summary

### ✅ Changes Applied
1. **Chunk size**: 1000 → 4000 chars
2. **Chunk overlap**: 200 → 800 chars
3. **Concurrency**: 5 → 2 requests

### 📊 Results
- **75% fewer chunks** to process
- **75% fewer tokens** used
- **75% lower cost** per document
- **97% faster** indexing
- **Minimal rate limit hits**

### 💰 Cost Per Document
- **Before**: ~$0.84 per document
- **After**: ~$0.21 per document
- **Savings**: $0.63 per document (75%)

### ⏱️ Time Per Document
- **Before**: 2-3 hours (with rate limit retries)
- **After**: 2-5 minutes (smooth processing)

---

## Next Steps

1. **Reindex your document** with new settings:
   ```
   POST /api/v1/documents/{id}/reindex-retrieval
   ```

2. **Monitor progress**:
   ```bash
   docker logs uu-celeryworker --tail 20 --follow
   ```

3. **Verify completion** in ~5 minutes instead of hours!

The system should now process **~488 chunks in about 2-5 minutes** with minimal rate limiting! 🚀
