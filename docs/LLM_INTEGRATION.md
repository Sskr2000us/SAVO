# Real LLM Integration Guide

## Overview

SAVO now supports three LLM providers:
1. **Mock** (default) - For testing without API costs
2. **OpenAI** - GPT-4 and GPT-3.5 models
3. **Anthropic** - Claude 3 models (Opus, Sonnet, Haiku)

## Quick Start

### 1. Choose Your Provider

Copy the example environment file:
```powershell
cd services\api
Copy-Item .env.example .env
```

Edit `.env` and set your provider:
```bash
SAVO_LLM_PROVIDER=openai  # or 'anthropic' or 'mock'
```

### 2. Add API Keys

#### For OpenAI:
1. Get API key from: https://platform.openai.com/api-keys
2. Add to `.env`:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4-turbo-preview
```

#### For Anthropic:
1. Get API key from: https://console.anthropic.com/account/keys
2. Add to `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 3. Install Dependencies

```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

New dependencies added:
- `openai>=1.0.0` - OpenAI Python SDK
- `anthropic>=0.18.0` - Anthropic Python SDK
- `httpx>=0.24.0` - Async HTTP client

### 4. Start Backend

```powershell
uvicorn app.main:app --reload --port 8000
```

The backend will now use your configured LLM provider.

## Provider Comparison

| Feature | Mock | OpenAI | Anthropic |
|---------|------|--------|-----------|
| Cost | Free | ~$0.01-0.10/request | ~$0.01-0.15/request |
| Speed | Instant | 2-5 seconds | 2-5 seconds |
| Quality | Fixed templates | High quality | High quality |
| JSON Schema | ✅ | ✅ | ✅ |
| Retry Logic | ✅ | ✅ | ✅ |
| Rate Limits | None | 10,000 TPM | 40,000 TPM |

## Model Options

### OpenAI Models
- **gpt-4-turbo-preview** (default) - Most capable, highest quality
  - Context: 128K tokens
  - Cost: $0.01/1K input, $0.03/1K output
- **gpt-4** - Previous generation, still excellent
  - Context: 8K tokens
  - Cost: $0.03/1K input, $0.06/1K output
- **gpt-3.5-turbo** - Faster, cheaper, good for testing
  - Context: 16K tokens
  - Cost: $0.0005/1K input, $0.0015/1K output

### Anthropic Models
- **claude-3-5-sonnet-20241022** (default) - Best balance
  - Context: 200K tokens
  - Cost: $0.003/1K input, $0.015/1K output
- **claude-3-opus-20240229** - Most capable
  - Context: 200K tokens
  - Cost: $0.015/1K input, $0.075/1K output
- **claude-3-sonnet-20240229** - Fast and cost-effective
  - Context: 200K tokens
  - Cost: $0.003/1K input, $0.015/1K output

## Reliability Features

### 1. Schema Validation
All LLM responses are validated against JSON schemas before being returned to the app.

```python
# In orchestrator.py
validate_json(result, schema)  # Throws SchemaValidationException if invalid
```

### 2. Retry Logic
If the LLM returns invalid JSON or fails schema validation:
- **Attempt 1**: Initial request
- **Attempt 2**: Retry with corrective instructions
- **After 2 attempts**: Return error status

```python
async def run_task(
    *,
    task_name: str,
    output_schema_name: str,
    context: Dict[str, Any],
    max_retries: int = 1  # One retry = 2 total attempts
) -> Dict[str, Any]:
```

### 3. Fail-Closed Behavior
The system never returns unvalidated data:
- ✅ Valid response → return to app
- ❌ Invalid after retry → return `status: "error"`
- ⚠️ LLM reports uncertainty → return `status: "needs_clarification"`

### 4. Error Handling

```python
# Non-JSON response
except json.JSONDecodeError as e:
    # Retry with: "Your response was not valid JSON"
    
# Schema validation failure
except SchemaValidationException as e:
    # Retry with: "Schema validation errors: [list of errors]"
    
# Network/API errors
except Exception as e:
    # Log error, retry if attempts remain
```

## Testing Each Provider

### Test with Mock (No API Key Required)
```powershell
$env:SAVO_LLM_PROVIDER="mock"
uvicorn app.main:app --reload --port 8000
```

Test daily planning:
```powershell
curl -X POST http://localhost:8000/plan/daily -H "Content-Type: application/json" -d "{}"
```

### Test with OpenAI
```powershell
$env:SAVO_LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="sk-your-key"
uvicorn app.main:app --reload --port 8000
```

### Test with Anthropic
```powershell
$env:SAVO_LLM_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="sk-ant-your-key"
uvicorn app.main:app --reload --port 8000
```

## Monitoring API Usage

### OpenAI
- Dashboard: https://platform.openai.com/usage
- View costs, requests, and rate limits

### Anthropic
- Dashboard: https://console.anthropic.com/settings/usage
- View costs, requests, and rate limits

## Timeouts

Configure timeout in `.env`:
```bash
LLM_TIMEOUT=60  # seconds
```

Passed to both providers:
```python
OpenAIClient(timeout=60)
AnthropicClient(timeout=60)
```

If a request exceeds timeout:
- Raises `httpx.TimeoutException`
- Orchestrator retries (if attempts remain)
- Returns error after max retries

## Error Messages

### When API Key is Missing
```
ValueError: OPENAI_API_KEY is required for OpenAI provider
ValueError: ANTHROPIC_API_KEY is required for Anthropic provider
```

**Fix**: Add key to `.env` file

### When Provider is Invalid
```
ValueError: Unsupported SAVO_LLM_PROVIDER: xyz. Use 'mock', 'openai', or 'anthropic'.
```

**Fix**: Set `SAVO_LLM_PROVIDER` to valid option

### When Schema Validation Fails
```json
{
  "status": "error",
  "error_message": "Schema validation failed after retry: missing required field 'menus'"
}
```

**Fix**: Check prompt pack schemas match LLM output

### When LLM Cannot Fulfill Request
```json
{
  "status": "needs_clarification",
  "needs_clarification_questions": [
    "What type of cuisine would you prefer?",
    "Do you have any dietary restrictions?"
  ]
}
```

**Fix**: This is expected behavior - UI should show questions to user

## Best Practices

### 1. Start with Mock
- Test all flows with mock provider first
- Verify schemas and data structures
- No API costs during development

### 2. Use GPT-3.5 for Testing
- Faster responses (1-2 seconds)
- Lower cost (~10x cheaper than GPT-4)
- Good enough for testing flows

### 3. Use GPT-4/Claude for Production
- Higher quality recipes and instructions
- Better understanding of complex constraints
- More reliable JSON generation

### 4. Monitor Costs
- Set up billing alerts in OpenAI/Anthropic dashboards
- Review usage weekly
- Consider caching responses for common requests

### 5. Handle Rate Limits
Both providers have rate limits:
- **OpenAI**: 10,000 TPM (tokens per minute)
- **Anthropic**: 40,000 TPM

If you hit rate limits:
- Add exponential backoff
- Implement request queuing
- Consider upgrading to higher tier

## Environment Variable Summary

```bash
# Provider selection (required)
SAVO_LLM_PROVIDER=mock|openai|anthropic

# OpenAI (required if provider=openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview  # optional

# Anthropic (required if provider=anthropic)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # optional

# Timeouts (optional)
LLM_TIMEOUT=60

# Prompt pack (optional override)
SAVO_PROMPT_PACK_PATH=docs/spec/prompt-pack.gpt-5.2.json
```

## Switching Providers

You can switch providers without code changes:

**Development**:
```powershell
$env:SAVO_LLM_PROVIDER="mock"
```

**Staging**:
```powershell
$env:SAVO_LLM_PROVIDER="openai"
$env:OPENAI_MODEL="gpt-3.5-turbo"
```

**Production**:
```powershell
$env:SAVO_LLM_PROVIDER="anthropic"
$env:ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"
```

## Troubleshooting

### Issue: "Module 'openai' has no attribute 'AsyncClient'"
**Solution**: Update dependencies
```powershell
pip install --upgrade openai anthropic httpx
```

### Issue: "Connection timeout"
**Solution**: Increase timeout
```bash
LLM_TIMEOUT=120
```

### Issue: "Rate limit exceeded"
**Solution**: 
1. Add delay between requests
2. Implement retry with exponential backoff
3. Upgrade API tier

### Issue: "Invalid JSON response"
**Solution**:
1. Check prompt pack schemas
2. Review system prompts
3. Try different model (GPT-4 > GPT-3.5 for JSON)

## Implementation Details

### OpenAI Integration
```python
async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},  # Force JSON
                "temperature": 0.7,
                "max_tokens": 4096,
            }
        )
```

### Anthropic Integration
```python
async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
    # Convert system messages separately
    system_content = "".join([m["content"] for m in messages if m["role"] == "system"])
    
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "system": system_content,
                "messages": [m for m in messages if m["role"] != "system"],
                "max_tokens": 4096,
            }
        )
```

## Next Steps

1. **Start with Mock**: Verify all flows work
2. **Test with GPT-3.5**: Quick validation with real LLM
3. **Upgrade to GPT-4**: Higher quality for production
4. **Consider Anthropic**: Claude 3.5 Sonnet offers excellent quality at lower cost
5. **Monitor Usage**: Set billing alerts and review usage patterns
6. **Optimize Prompts**: Refine based on actual LLM responses
7. **Cache Common Responses**: Store frequently requested plans

## Support

For issues with:
- **OpenAI**: https://help.openai.com/
- **Anthropic**: https://support.anthropic.com/
- **SAVO Integration**: Check logs in `uvicorn` terminal output
