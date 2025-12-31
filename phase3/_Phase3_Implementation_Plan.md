# HA-Autopilot Phase 3: Natural Language Translation Layer

## Technical Planning Document

**Project:** HA-Autopilot (Proactive Automation Architect)  
**Phase:** 3 - LLM Integration for Pattern Translation  
**Version:** 1.0 Draft  
**Prerequisites:** Phase 1 (Data Pipeline) and Phase 2 (Pattern Recognition) complete

---

## 1. Phase Objective

Convert discovered statistical patterns into natural language suggestions that users actually want to answer. The pattern `Trigger: TV_On (20:00-23:00), Action: Light_50%, Confidence: 0.95` becomes "Should I dim the lights automatically when you start watching TV in the evening?"

This phase bridges raw pattern data and human interaction. The LLM reads structured JSON, generates conversational questions, handles user responses, and prepares approved patterns for automation generation in Phase 4.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Phase 3 Component Stack                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │  Pattern Input  │───▶│   LLM Router    │───▶│   Response   │ │
│  │  (Phase 2 JSON) │    │   (Provider     │    │   Parser     │ │
│  │                 │    │    Abstraction) │    │              │ │
│  └─────────────────┘    └────────┬────────┘    └──────┬───────┘ │
│                                  │                     │         │
│                      ┌───────────┴───────────┐        │         │
│                      ▼           ▼           ▼        │         │
│              ┌───────────┐ ┌──────────┐ ┌─────────┐   │         │
│              │  Ollama   │ │  Claude  │ │  GPT    │   │         │
│              │  (Local)  │ │  API     │ │  API    │   │         │
│              └───────────┘ └──────────┘ └─────────┘   │         │
│                                                       │         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────▼────────┐ │
│  │   Suggestion    │◀───│   Template      │◀───│   Output     │ │
│  │   Registry      │    │   Engine        │    │   Formatter  │ │
│  └────────┬────────┘    └─────────────────┘    └──────────────┘ │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │   Notification  │───▶│   Feedback      │                     │
│  │   Service       │    │   Handler       │                     │
│  └─────────────────┘    └─────────────────┘                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Provider Abstraction Layer

### 3.1 Design Rationale

Users run different AI setups. Some prefer local models for privacy. Others want cloud API access for better results. The system must support multiple providers without code changes.

### 3.2 Supported Providers

| Provider | Type | Models | Use Case |
|----------|------|--------|----------|
| Ollama | Local | Llama 3.x, Mistral, Gemma 2 | Privacy-first, no API costs |
| Claude API | Cloud | Claude Sonnet 4, Haiku 4 | High-quality suggestions |
| OpenAI | Cloud | GPT-4o, GPT-4o-mini | Alternative cloud option |
| Google Gemini | Cloud | Gemini 2.5 Flash/Pro | Google ecosystem users |
| Custom Endpoint | Either | Any OpenAI-compatible | Self-hosted alternatives |

### 3.3 Provider Interface Specification

```python
# Abstract interface all providers must implement
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str) -> str:
        """Send prompt to LLM, return text response."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verify provider is reachable and responding."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> dict:
        """Return model limits, token counts, features."""
        pass
```

### 3.4 Required Code Components

**Files to Create:**

- `llm_providers/__init__.py` - Provider registration and factory
- `llm_providers/base.py` - Abstract base class and common utilities
- `llm_providers/ollama.py` - Local Ollama integration
- `llm_providers/anthropic.py` - Claude API integration
- `llm_providers/openai.py` - OpenAI/GPT integration
- `llm_providers/google.py` - Gemini API integration
- `llm_providers/custom.py` - OpenAI-compatible endpoint handler

**Configuration Schema:**

```yaml
ha_autopilot:
  llm:
    provider: "ollama"  # ollama | anthropic | openai | google | custom
    
    ollama:
      host: "http://localhost:11434"
      model: "llama3.2"
      timeout: 60
      
    anthropic:
      api_key: !secret anthropic_api_key
      model: "claude-sonnet-4-20250514"
      
    openai:
      api_key: !secret openai_api_key
      model: "gpt-4o-mini"
      
    google:
      api_key: !secret google_api_key
      model: "gemini-2.5-flash"
      
    custom:
      endpoint: "http://192.168.1.50:8080/v1/chat/completions"
      api_key: !secret custom_llm_key
      model: "local-mistral"
```

---

## 4. Prompt Engineering System

### 4.1 Prompt Architecture

Three-layer prompt structure ensures consistent, high-quality output:

1. **System Prompt** - Sets persona, constraints, output format
2. **Context Prompt** - Injects home-specific entity names, user preferences
3. **Task Prompt** - The actual pattern data to translate

### 4.2 System Prompt Template

```
You are a helpful smart home assistant analyzing behavior patterns. Your job is to 
translate statistical pattern data into natural, conversational questions.

Rules:
- Write suggestions as yes/no questions
- Use casual, friendly language
- Reference devices by their friendly names
- Include the confidence level naturally (e.g., "almost always", "usually", "often")
- Keep questions under 30 words
- Never mention technical terms like "confidence score" or "support value"
- If the pattern seems trivial (< 5 occurrences), note that it's a recent observation

Output format (JSON only, no markdown):
{
  "question": "...",
  "explanation": "...",
  "auto_enable_safe": true/false
}
```

### 4.3 Context Injection

Before generating suggestions, the system injects:

- Entity friendly names (from HA entity registry)
- Area assignments (kitchen, bedroom, living room)
- User timezone and locale
- Previously rejected pattern types (to avoid re-suggesting)

**Context Template:**

```
Home Context:
- Location: {timezone}, {locale}
- Relevant Devices:
  {entity_id}: "{friendly_name}" in {area}
  ...
- User has previously rejected patterns involving: {rejected_pattern_types}
```

### 4.4 Task Prompt Template

```
Translate this pattern into a suggestion:

Pattern Data:
- Type: {pattern_type}
- Trigger: {trigger_entities} during {time_window}
- Action: {action_entity} changes to {target_state}
- Confidence: {confidence_percent}%
- Observed: {occurrence_count} times over {observation_days} days

Generate a friendly question asking if this should be automated.
```

### 4.5 Required Code Components

**Files to Create:**

- `prompts/__init__.py` - Prompt template loader
- `prompts/system_prompts.py` - Base system prompts per use case
- `prompts/context_builder.py` - Dynamic context injection
- `prompts/task_templates.py` - Pattern-to-prompt formatters
- `prompts/templates/` - Jinja2 template files for customization

---

## 5. Pattern Translation Pipeline

### 5.1 Pipeline Stages

```
Phase 2 Output ──▶ Pattern Loader ──▶ Context Enrichment ──▶ Batch Grouping
                                                                    │
                                                                    ▼
User Notification ◀── Suggestion Store ◀── Response Parse ◀── LLM Call
```

### 5.2 Translation Workflow

**Step 1: Load Patterns**

Read `patterns_for_review.json` from Phase 2 output directory. Filter patterns meeting suggestion threshold (score ≥ 0.70, not previously rejected).

**Step 2: Enrich Context**

For each pattern:
- Resolve entity IDs to friendly names via HA entity registry API
- Determine area assignments
- Check existing automations for conflicts
- Query rejection history from suggestion database

**Step 3: Batch for LLM**

Group patterns to minimize API calls:
- 3-5 patterns per request for local models
- 5-10 patterns per request for cloud APIs
- Respect token limits per provider

**Step 4: Generate Suggestions**

Send batched prompts to configured LLM provider. Parse JSON responses.

**Step 5: Store Suggestions**

Write generated suggestions to database with:
- Pattern ID reference
- Generated question text
- Explanation text
- Auto-enable safety flag
- Generation timestamp
- Provider/model used

**Step 6: Notify User**

Create persistent notification in Home Assistant with actionable buttons.

### 5.3 Required Code Components

**Files to Create:**

- `translator/__init__.py` - Pipeline orchestrator
- `translator/loader.py` - Phase 2 JSON parser
- `translator/enricher.py` - Context data fetcher (HA API calls)
- `translator/batcher.py` - Token-aware batching logic
- `translator/generator.py` - LLM call coordinator
- `translator/parser.py` - Response validation and extraction
- `translator/store.py` - Database persistence

---

## 6. Suggestion Management System

### 6.1 Database Schema

```sql
CREATE TABLE llm_suggestions (
    id INTEGER PRIMARY KEY,
    pattern_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    explanation TEXT,
    auto_enable_safe BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    response_source TEXT,  -- notification, dashboard, voice
    llm_provider TEXT,
    llm_model TEXT,
    prompt_tokens INTEGER,
    response_tokens INTEGER,
    FOREIGN KEY (pattern_id) REFERENCES discovered_patterns(id)
);

CREATE TABLE suggestion_feedback (
    id INTEGER PRIMARY KEY,
    suggestion_id INTEGER NOT NULL,
    feedback_type TEXT,  -- approved, rejected, edited, snoozed
    feedback_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (suggestion_id) REFERENCES llm_suggestions(id)
);

CREATE INDEX idx_suggestions_status ON llm_suggestions(status);
CREATE INDEX idx_suggestions_pattern ON llm_suggestions(pattern_id);
```

### 6.2 Suggestion Lifecycle

```
                    ┌─────────────────────────────┐
                    │        PENDING              │
                    │  (Awaiting user response)   │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │    APPROVED    │   │    REJECTED    │   │    SNOOZED     │
     │ (Send to Ph4)  │   │ (Mark pattern) │   │ (Re-ask later) │
     └────────────────┘   └────────────────┘   └───────┬────────┘
                                                       │
                                                       ▼
                                               ┌────────────────┐
                                               │    EXPIRED     │
                                               │ (Snooze limit) │
                                               └────────────────┘
```

### 6.3 Required Code Components

**Files to Create:**

- `suggestions/__init__.py` - Service registration
- `suggestions/models.py` - SQLAlchemy/dataclass models
- `suggestions/repository.py` - Database operations
- `suggestions/lifecycle.py` - State transition logic
- `suggestions/services.yaml` - HA service definitions

---

## 7. Notification and Response System

### 7.1 Notification Channels

| Channel | Method | User Action |
|---------|--------|-------------|
| Persistent Notification | HA `persistent_notification.create` | View in sidebar |
| Mobile Push | Companion App with actions | Tap to approve/reject |
| Dashboard Card | Custom Lovelace card | Button interactions |
| Voice | Assist pipeline integration | "Yes" / "No" responses |

### 7.2 Mobile Notification Format

```yaml
service: notify.mobile_app_phone
data:
  title: "New Automation Suggestion"
  message: "{{ suggestion.question }}"
  data:
    actions:
      - action: "APPROVE_{{ suggestion.id }}"
        title: "Yes, automate it"
      - action: "REJECT_{{ suggestion.id }}"
        title: "No thanks"
      - action: "SNOOZE_{{ suggestion.id }}"
        title: "Ask later"
    tag: "ha_autopilot_suggestion_{{ suggestion.id }}"
```

### 7.3 Event Handling

Listen for notification action events and route to feedback handler:

```python
# Event triggers
EVENT_MOBILE_APP_NOTIFICATION_ACTION = "mobile_app_notification_action"
EVENT_PERSISTENT_NOTIFICATION_ACTION = "persistent_notification_action"

# Action patterns
APPROVE_PATTERN = re.compile(r"APPROVE_(\d+)")
REJECT_PATTERN = re.compile(r"REJECT_(\d+)")
SNOOZE_PATTERN = re.compile(r"SNOOZE_(\d+)")
```

### 7.4 Required Code Components

**Files to Create:**

- `notifications/__init__.py` - Notification service
- `notifications/builders.py` - Message formatting per channel
- `notifications/dispatcher.py` - Multi-channel sending logic
- `notifications/event_listener.py` - Response event handler
- `notifications/rate_limiter.py` - Prevent notification spam

---

## 8. Security Implementation

### 8.1 Threat Model

| Threat | Risk | Mitigation |
|--------|------|------------|
| API Key Exposure | High | Store in HA secrets, never log |
| Prompt Injection via Entity Names | Medium | Sanitize all entity data before prompt inclusion |
| LLM Generates Malicious YAML | High | Phase 4 concern, but validate suggestions here |
| Denial of Service (LLM overload) | Medium | Rate limiting, queue management |
| Data Exfiltration via Cloud APIs | Medium | Local provider option, data minimization |
| Man-in-the-Middle on API Calls | Medium | TLS verification, certificate pinning option |

### 8.2 API Key Management

```python
# Never hardcode keys
api_key = hass.config.api_key_from_secrets("anthropic_api_key")

# Never log keys
logger.debug(f"Using provider {provider}")  # Good
logger.debug(f"Key: {api_key[:4]}...")  # Bad - even partial exposure

# Validate key format before use
def validate_anthropic_key(key: str) -> bool:
    return key.startswith("sk-ant-") and len(key) > 40
```

### 8.3 Input Sanitization

Entity names come from user configuration and could contain injection attempts:

```python
def sanitize_for_prompt(text: str) -> str:
    """Remove potential prompt injection patterns."""
    # Strip control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Escape sequences that might confuse LLM parsing
    text = text.replace('```', '`​`​`')  # Zero-width space injection
    text = text.replace('</s>', '')  # Model special tokens
    text = text.replace('<|', '')
    text = text.replace('|>', '')
    
    # Length limit
    return text[:200]
```

### 8.4 Output Validation

Before storing LLM responses:

```python
def validate_suggestion_response(response: dict) -> bool:
    """Ensure LLM output meets safety requirements."""
    required_fields = ["question", "explanation", "auto_enable_safe"]
    
    # Structure check
    if not all(field in response for field in required_fields):
        return False
    
    # Length limits
    if len(response["question"]) > 500:
        return False
    if len(response["explanation"]) > 2000:
        return False
    
    # Type validation
    if not isinstance(response["auto_enable_safe"], bool):
        return False
    
    # Content check - no code blocks in suggestions
    if "```" in response["question"] or "```" in response["explanation"]:
        return False
    
    return True
```

### 8.5 Rate Limiting

Prevent runaway LLM costs and system overload:

```python
class RateLimiter:
    def __init__(self):
        self.calls_per_hour = 60  # Configurable
        self.calls_per_day = 500
        self.hourly_count = 0
        self.daily_count = 0
        self.last_reset_hour = datetime.now().hour
        self.last_reset_day = datetime.now().day
    
    def can_call(self) -> bool:
        self._maybe_reset()
        return (self.hourly_count < self.calls_per_hour and 
                self.daily_count < self.calls_per_day)
    
    def record_call(self):
        self.hourly_count += 1
        self.daily_count += 1
```

### 8.6 Data Minimization for Cloud APIs

When using cloud providers, limit transmitted data:

```python
def minimize_pattern_data(pattern: dict) -> dict:
    """Strip unnecessary fields before sending to cloud LLM."""
    return {
        "type": pattern["type"],
        "trigger": pattern["trigger"],  # Already pseudonymized
        "action": pattern["action"],
        "confidence": pattern["metrics"]["confidence"],
        "count": pattern["metrics"]["occurrence_count"]
    }
    # Excluded: raw timestamps, user identifiers, full metrics
```

### 8.7 Required Code Components

**Files to Create:**

- `security/__init__.py` - Security utilities
- `security/key_manager.py` - API key handling
- `security/sanitizer.py` - Input/output cleaning
- `security/rate_limiter.py` - Call throttling
- `security/validator.py` - Response validation
- `security/audit_log.py` - Security event logging

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Provider Tests:**
- Each provider initializes correctly
- Health check returns expected status
- Malformed responses handled gracefully
- Timeout behavior correct

**Prompt Tests:**
- Template rendering produces valid prompts
- Context injection escapes special characters
- Token count estimation accurate

**Parser Tests:**
- Valid JSON extracted from LLM responses
- Invalid responses rejected
- Edge cases (empty, truncated, malformed) handled

### 9.2 Integration Tests

**End-to-End Flow:**
1. Load sample pattern file
2. Generate suggestions via test provider (mocked)
3. Verify database records created
4. Simulate notification response
5. Confirm feedback recorded

**Provider Integration (optional, uses real APIs):**
- Ollama connection test with local model
- Cloud API authentication verification
- Response quality spot check

### 9.3 Mock Provider for Testing

```python
class MockLLMProvider(LLMProvider):
    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.call_log = []
    
    async def generate(self, prompt: str, system: str) -> str:
        self.call_log.append({"prompt": prompt, "system": system})
        
        # Return canned response based on pattern ID in prompt
        pattern_id = extract_pattern_id(prompt)
        if pattern_id in self.responses:
            return json.dumps(self.responses[pattern_id])
        
        # Default response
        return json.dumps({
            "question": "Should I automate this for you?",
            "explanation": "Test explanation",
            "auto_enable_safe": True
        })
```

### 9.4 Required Test Files

- `tests/__init__.py`
- `tests/test_providers.py`
- `tests/test_prompts.py`
- `tests/test_translator.py`
- `tests/test_suggestions.py`
- `tests/test_notifications.py`
- `tests/test_security.py`
- `tests/conftest.py` - Pytest fixtures
- `tests/fixtures/` - Sample pattern files, mock responses

---

## 10. Configuration Reference

### 10.1 Complete Configuration Schema

```yaml
ha_autopilot:
  # Phase 3 LLM Settings
  llm:
    provider: "ollama"
    
    # Provider-specific settings (see section 3.4)
    ollama:
      host: "http://localhost:11434"
      model: "llama3.2"
      timeout: 60
      context_length: 8192
      
    anthropic:
      api_key: !secret anthropic_api_key
      model: "claude-sonnet-4-20250514"
      max_tokens: 1024
      
    openai:
      api_key: !secret openai_api_key
      model: "gpt-4o-mini"
      max_tokens: 1024
      
    google:
      api_key: !secret google_api_key
      model: "gemini-2.5-flash"
      
    custom:
      endpoint: "http://localhost:8080/v1/chat/completions"
      api_key: !secret custom_llm_key
      model: "local-model"
  
  # Translation settings
  translation:
    batch_size: 5
    min_pattern_score: 0.70
    retry_count: 3
    retry_delay: 5  # seconds
    
  # Notification settings
  notifications:
    enabled: true
    channels:
      - persistent_notification
      - mobile_app
    mobile_targets:
      - notify.mobile_app_phone
    max_pending: 10  # Don't queue more than this
    cooldown_hours: 24  # After rejection, wait before re-suggesting
    
  # Security settings
  security:
    rate_limit:
      calls_per_hour: 60
      calls_per_day: 500
    sanitize_inputs: true
    validate_outputs: true
    audit_logging: true
    
  # Schedule settings
  schedule:
    translation_time: "04:00:00"  # Run daily at 4 AM
    suggestion_expiry_days: 7
```

### 10.2 Services Exposed

```yaml
# services.yaml
generate_suggestions:
  name: Generate Suggestions
  description: Manually trigger suggestion generation from pending patterns
  fields:
    max_patterns:
      name: Maximum Patterns
      description: Limit number of patterns to process
      default: 20
      selector:
        number:
          min: 1
          max: 100

approve_suggestion:
  name: Approve Suggestion
  description: Approve a pending suggestion
  fields:
    suggestion_id:
      name: Suggestion ID
      required: true
      selector:
        number:

reject_suggestion:
  name: Reject Suggestion
  description: Reject a pending suggestion
  fields:
    suggestion_id:
      name: Suggestion ID
      required: true
      selector:
        number:
    reason:
      name: Reason
      description: Optional rejection reason
      selector:
        text:

test_llm_connection:
  name: Test LLM Connection
  description: Verify LLM provider is reachable and responding
```

---

## 11. File Structure Summary

```
custom_components/ha_autopilot/
├── __init__.py                 # Component setup
├── manifest.json               # Component metadata
├── services.yaml               # Service definitions
├── const.py                    # Constants and defaults
│
├── llm_providers/
│   ├── __init__.py             # Provider factory
│   ├── base.py                 # Abstract base class
│   ├── ollama.py               # Ollama integration
│   ├── anthropic.py            # Claude API
│   ├── openai.py               # OpenAI/GPT
│   ├── google.py               # Gemini
│   └── custom.py               # OpenAI-compatible endpoints
│
├── prompts/
│   ├── __init__.py             # Prompt loader
│   ├── system_prompts.py       # Base system prompts
│   ├── context_builder.py      # Context injection
│   ├── task_templates.py       # Pattern formatters
│   └── templates/
│       ├── suggestion.j2       # Suggestion generation template
│       └── batch.j2            # Multi-pattern batch template
│
├── translator/
│   ├── __init__.py             # Pipeline orchestrator
│   ├── loader.py               # Phase 2 JSON parser
│   ├── enricher.py             # HA API context fetcher
│   ├── batcher.py              # Token-aware batching
│   ├── generator.py            # LLM call coordinator
│   ├── parser.py               # Response extraction
│   └── store.py                # Database persistence
│
├── suggestions/
│   ├── __init__.py             # Suggestion service
│   ├── models.py               # Data models
│   ├── repository.py           # Database operations
│   └── lifecycle.py            # State transitions
│
├── notifications/
│   ├── __init__.py             # Notification service
│   ├── builders.py             # Message formatting
│   ├── dispatcher.py           # Multi-channel sending
│   ├── event_listener.py       # Response handler
│   └── rate_limiter.py         # Spam prevention
│
├── security/
│   ├── __init__.py             # Security utilities
│   ├── key_manager.py          # API key handling
│   ├── sanitizer.py            # Input/output cleaning
│   ├── rate_limiter.py         # Call throttling
│   ├── validator.py            # Response validation
│   └── audit_log.py            # Security event logging
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Fixtures
    ├── test_providers.py
    ├── test_prompts.py
    ├── test_translator.py
    ├── test_suggestions.py
    ├── test_notifications.py
    ├── test_security.py
    └── fixtures/
        ├── sample_patterns.json
        └── mock_responses.json
```

---

## 12. Implementation Sequence

### 12.1 Sprint 1: Foundation (Week 1)

**Goal:** LLM provider abstraction working with at least one provider

**Tasks:**
1. Create base provider interface and factory
2. Implement Ollama provider (simplest local option)
3. Build health check service
4. Write provider unit tests
5. Create configuration schema and validation

**Deliverable:** `test_llm_connection` service works

### 12.2 Sprint 2: Prompts and Translation (Week 2)

**Goal:** Patterns convert to suggestions via LLM

**Tasks:**
1. Design prompt templates (system, context, task)
2. Build context enrichment from HA entity registry
3. Implement translation pipeline (loader → enricher → generator → parser)
4. Create suggestion database schema
5. Write pipeline integration tests

**Deliverable:** Sample pattern file produces stored suggestions

### 12.3 Sprint 3: Additional Providers (Week 3)

**Goal:** Cloud API support for users who want it

**Tasks:**
1. Implement Anthropic provider
2. Implement OpenAI provider
3. Implement Google Gemini provider
4. Implement custom endpoint provider
5. Add provider-specific configuration validation
6. Write provider integration tests (mocked and live)

**Deliverable:** All five providers pass health checks

### 12.4 Sprint 4: Notifications and Feedback (Week 4)

**Goal:** Users receive and respond to suggestions

**Tasks:**
1. Build notification dispatcher (persistent + mobile)
2. Implement event listener for responses
3. Create feedback recording logic
4. Build suggestion lifecycle state machine
5. Add rate limiting for notifications
6. Write end-to-end tests

**Deliverable:** Complete suggestion flow from pattern to user response

### 12.5 Sprint 5: Security and Polish (Week 5)

**Goal:** Production-ready security posture

**Tasks:**
1. Implement input sanitization
2. Add output validation
3. Build rate limiter for LLM calls
4. Create audit logging
5. Security review and penetration testing
6. Documentation and README

**Deliverable:** Security checklist complete, ready for Phase 4 handoff

---

## 13. Phase 4 Handoff Specification

### 13.1 Output to Phase 4

When a suggestion is approved, Phase 3 writes to the handoff queue:

```json
{
  "suggestion_id": 42,
  "pattern_id": 17,
  "pattern_data": {
    "type": "association",
    "trigger": [
      {"entity_id": "media_player.living_room_tv", "state": "playing"},
      {"time_bucket": "evening"}
    ],
    "action": {
      "entity_id": "light.living_room",
      "service": "light.turn_on",
      "service_data": {"brightness_pct": 20}
    },
    "confidence": 0.94
  },
  "user_approved_at": "2025-01-15T10:30:00Z",
  "auto_enable_safe": true
}
```

### 13.2 Feedback Loop

Phase 4 reports back:
- Automation ID if successfully created
- Error details if generation failed
- User can then track which suggestions became real automations

---

## 14. Potential Enhancements

These features extend Phase 3 beyond minimum viable functionality. Prioritize based on user feedback after initial deployment.

### 14.1 Conversational Refinement

Allow multi-turn conversations with the LLM to refine suggestions:

"Should I dim the lights when you watch TV?"  
*User: "Only on weekdays"*  
"Got it. Should I dim the lights when you watch TV on weekday evenings?"

**Complexity:** High. Requires conversation state management and more sophisticated prompting.

### 14.2 Suggestion Scheduling Preferences

Let users configure when they receive suggestions:
- Only during certain hours
- Batch all suggestions into a daily digest
- Different channels for different urgency levels

**Complexity:** Medium. Adds scheduling logic and user preference storage.

### 14.3 Explanation Depth Levels

Generate multiple explanation versions:
- **Brief:** "TV on → lights dim"
- **Standard:** "I noticed you usually dim the living room lights when watching TV in the evening."
- **Detailed:** "Over the past 21 days, you've dimmed the living room lights to 20% within 2 minutes of starting the TV 48 times (94% consistency), typically between 8 PM and 11 PM."

**Complexity:** Low. Additional prompt templates.

### 14.4 Voice Assistant Integration

Deep integration with Home Assistant Assist:
- Read suggestions aloud during morning routines
- Accept voice responses: "Yes, do that" / "No, skip it"
- Conversational follow-up questions

**Complexity:** High. Requires Assist pipeline customization.

### 14.5 Suggestion Confidence Calibration

Track accuracy of "auto_enable_safe" flag over time. If users frequently reject suggestions marked safe, recalibrate the LLM prompt or add post-processing rules.

**Complexity:** Medium. Requires feedback analysis pipeline.

### 14.6 Multi-Language Support

Generate suggestions in user's preferred language. Ollama and cloud providers support multiple languages, but prompt templates need translation.

**Complexity:** Medium. Prompt localization and language detection.

### 14.7 Suggestion Grouping

Related patterns (e.g., all bedtime behaviors) could be presented as a single "routine" suggestion rather than individual automations.

**Complexity:** High. Requires pattern clustering and routine detection logic.

### 14.8 LLM Response Caching

Cache identical pattern translations to reduce API calls. Hash pattern data and check cache before calling LLM.

**Complexity:** Low. Standard caching implementation.

### 14.9 A/B Testing for Prompts

Test different prompt variations to optimize acceptance rates. Track which prompt versions lead to more approvals.

**Complexity:** Medium. Requires experimentation framework.

### 14.10 Privacy Dashboard

Show users exactly what data was sent to cloud LLMs:
- Full prompt history
- Response logs
- Option to delete all cloud-sent data

**Complexity:** Medium. UI component plus data retention policy.

---

## 15. Dependencies

### 15.1 Python Packages

```
# requirements.txt additions for Phase 3
aiohttp>=3.8.0          # Async HTTP for API calls
jinja2>=3.0.0           # Prompt templating
pydantic>=2.0.0         # Data validation
tenacity>=8.0.0         # Retry logic
tiktoken>=0.5.0         # Token counting for OpenAI
anthropic>=0.18.0       # Anthropic SDK (optional)
openai>=1.0.0           # OpenAI SDK (optional)
google-generativeai>=0.3.0  # Google Gemini SDK (optional)
```

### 15.2 External Services

- **Ollama:** Self-hosted, requires separate installation
- **Cloud APIs:** Require account creation and API keys
- **Home Assistant:** Version 2024.1.0+ for entity registry access

---

## 16. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Suggestion Generation Success Rate | > 95% | Patterns processed without error |
| User Response Rate | > 60% | Suggestions that receive any response |
| Approval Rate | > 40% | Suggestions approved by users |
| LLM Call Latency (local) | < 5 seconds | 95th percentile |
| LLM Call Latency (cloud) | < 3 seconds | 95th percentile |
| False Positive Rate | < 20% | Suggestions users find irrelevant |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-XX | Initial planning document |
