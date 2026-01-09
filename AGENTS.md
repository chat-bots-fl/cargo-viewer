# AGENTS.md — Telegram Bot Project Playbook

**Version:** 1.0  
**Target:** Coding agents (Cline, Claude, GPT-4)  
**Approach:** Contract-based programming with Python docstrings  
**Last Updated:** 2025-12-16

---

## Core Philosophy

**Contract-First Design:** Every function has a contract BEFORE implementation.

The contract is a **docstring comment block** placed DIRECTLY ABOVE function declaration:
1. **GOAL** – What this function does (one sentence)
2. **Parameters** – Input types and constraints
3. **Returns** – Output type and meaning
4. **Raises** – What can go wrong
5. **Guarantees** – What is always true after execution

The docstring INSIDE the function explains the **algorithm briefly** (not step-by-step, just the idea).

**Why this works:**
- GPT reads the contract BEFORE seeing implementation
- GPT understands intent before code
- Casual magic: GPT generates code that satisfies the contract
- Easy to verify: Does generated code satisfy contract?

---

## 1. Contract-Based Programming Pattern

### Template: Function Contract (Above Declaration)

```python
"""
GOAL: [One sentence: what this does]

PARAMETERS:
  param1: [type] - [meaning] - [constraints]
  param2: [type] - [meaning] - [constraints]

RETURNS:
  [type] - [meaning] - [constraints/guarantee]

RAISES:
  [ExceptionType]: [When and why]
  [ExceptionType]: [When and why]

GUARANTEES:
  - [Always true after execution]
  - [Always true after execution]
"""
```

### Example 1: Pricing Calculator

```python
"""
GOAL: Apply percentage discount to prices, ensuring no price falls below 0.01 RUB.

PARAMETERS:
  prices: List[Decimal] - Current prices per item - All >= 0.01
  discount_percent: float - Discount percentage - 0 <= value <= 100
  min_price: Decimal - Minimum allowed price - Must be positive, default 0.01

RETURNS:
  List[Decimal] - Discounted prices, same order as input - All >= min_price

RAISES:
  ValueError: If prices list is empty
  ValueError: If any price < 0.01 before discount
  ValueError: If discount_percent outside [0, 100]

GUARANTEES:
  - Returned list has same length as input
  - No price falls below min_price
  - All prices rounded to 2 decimal places
  - Original prices not modified
"""
async def apply_discount(
    prices: List[Decimal],
    discount_percent: float,
    min_price: Decimal = Decimal("0.01")
) -> List[Decimal]:
    """
    Multiply each price by (1 - discount%), then clamp to min_price.
    Uses Decimal arithmetic for kopeck-level precision.
    """
    # Implementation here
```

### Example 2: Wildberries Inventory Sync

```python
"""
GOAL: Fetch current inventory from Wildberries API and update local database 
      without losing data on partial failures.

PARAMETERS:
  api_client: WildberriesClient - Authenticated API client - Not None
  db_session: AsyncSession - Database session - Must be open
  product_ids: Optional[List[int]] - Which products to sync - None = all
  max_retries: int - How many times to retry on failure - >= 1

RETURNS:
  SyncResult - Contains success status, items synced, errors - Never None

RAISES:
  ConnectionError: If API unreachable after all retries
  AuthError: If credentials invalid

GUARANTEES:
  - Returned SyncResult contains accurate count of processed items
  - On partial failure, synced items persist, failed items logged
  - Original DB state recoverable from error logs
  - Function is idempotent (safe to call twice with same params)
"""
async def sync_inventory_from_api(
    api_client: WildberriesClient,
    db_session: AsyncSession,
    product_ids: Optional[List[int]] = None,
    max_retries: int = 3
) -> SyncResult:
    """
    Fetch inventory in batches with exponential backoff retries, 
    then batch-insert/update to database while maintaining audit log.
    """
    # Implementation here
```

### Example 3: Telegram Message Handler

```python
"""
GOAL: Process incoming Telegram message, validate user permissions, 
      and route to appropriate handler without losing message context.

PARAMETERS:
  message: Message - Telegram message object - Not None, has user_id
  handlers_map: Dict[str, Callable] - Command to handler mapping - Not empty
  user_context: UserContext - Cache of user permissions - Can be None (fetch fresh)

RETURNS:
  MessageResponse - Response message + metadata - Never None

RAISES:
  PermissionError: If user lacks required permission
  HandlerNotFound: If command not in handlers_map
  InvalidMessage: If message missing required fields

GUARANTEES:
  - Every message processed exactly once (no duplicates)
  - Error responses are user-friendly (not stack traces)
  - User context is updated in cache
  - Message logging contains full trace for debugging
"""
async def handle_user_message(
    message: Message,
    handlers_map: Dict[str, Callable],
    user_context: Optional[UserContext] = None
) -> MessageResponse:
    """
    Check permissions via cache or fetch, validate command exists, 
    then invoke handler while catching exceptions and logging context.
    """
    # Implementation here
```

---

## 2. Docstring Algorithm (Inside Function)

**Rule:** Write algorithm in **1-2 sentences**, NOT step-by-step.

### What to Write

```python
"""
[Describe IDEA, not steps]
[Why this approach, what is key insight]
"""
```

### What NOT to Write

```python
"""
1. Validate input
2. Loop through items
3. Apply calculation
4. Return result
"""
# ❌ Too detailed, step-by-step, looks like pseudocode
```

### Good Examples

```python
async def apply_discount(prices, discount_percent, min_price):
    """
    Multiply each price by discount factor, then clamp result to minimum.
    Uses Decimal for precise kopeck-level arithmetic.
    """
    # Code

async def sync_inventory_from_api(api_client, db_session, product_ids, max_retries):
    """
    Fetch inventory from API in batches with exponential backoff, 
    then atomic bulk-insert to database with failure recovery.
    """
    # Code

async def handle_user_message(message, handlers_map, user_context):
    """
    Check permissions (cached or fresh), route to handler, 
    catch exceptions and return user-friendly error or result.
    """
    # Code

def validate_email(email: str) -> bool:
    """
    Match against RFC 5322 pattern, then verify domain has MX record.
    """
    # Code
```

---

## 3. Type Hints + Contracts = Complete Intent

**Before GPT sees implementation, it knows:**

```
FROM CONTRACT:
- What inputs are allowed
- What outputs are guaranteed
- What can fail and how
- What is always true

FROM TYPE HINTS:
- Exact data types
- Nullability
- Collections and their contents

FROM ALGORITHM DOCSTRING:
- High-level approach
- Why this strategy
- Key insight
```

**GPT fills in the rest.** The code becomes obvious.

---

## 4. Implementation Example: Full Function

```python
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from datetime import datetime

"""
GOAL: Apply seasonal pricing markup to products, preventing price inversion 
      and maintaining audit trail of all changes.

PARAMETERS:
  prices: List[Decimal] - Current prices - All >= 0.01
  factor: Decimal - Markup multiplier - 0.5 <= value <= 2.0
  context: OperationContext - Who/when this happened - Not None
  min_price: Decimal - Minimum allowed result - Usually 0.01

RETURNS:
  List[Decimal] - New prices after markup - Same length, all >= min_price

RAISES:
  ValueError: If prices empty or any < 0.01
  ValueError: If factor outside [0.5, 2.0]
  TypeError: If context missing required fields

GUARANTEES:
  - Output length equals input length
  - Prices rounded to 2 decimal places (kopeck precision)
  - No price falls below min_price
  - Audit log created with operator_id, timestamp, original/new values
  - Idempotent: calling twice with same inputs produces same result
"""
async def apply_seasonal_markup(
    prices: List[Decimal],
    factor: Decimal,
    context: OperationContext,
    min_price: Decimal = Decimal("0.01")
) -> List[Decimal]:
    """
    Multiply each price by factor, then floor to min_price if needed.
    Log every change with operator_id and timestamp for compliance.
    """
    
    # Validation (from contract)
    if not prices:
        raise ValueError("Price list cannot be empty")
    
    if factor < Decimal("0.5") or factor > Decimal("2.0"):
        raise ValueError(f"Factor must be [0.5, 2.0], got {factor}")
    
    if not hasattr(context, 'operator_id') or not hasattr(context, 'timestamp'):
        raise TypeError("Context must have operator_id and timestamp")
    
    # Algorithm (from docstring idea)
    new_prices = []
    for original in prices:
        if original < min_price:
            raise ValueError(f"Price {original} below minimum {min_price}")
        
        # Apply factor
        new_price = (original * factor).quantize(
            Decimal("0.01"), 
            rounding=ROUND_HALF_UP
        )
        
        # Clamp to minimum
        if new_price < min_price:
            new_price = min_price
        
        new_prices.append(new_price)
    
    # Audit logging (from guarantees)
    await audit_log(
        operator_id=context.operator_id,
        timestamp=context.timestamp,
        operation="seasonal_markup",
        original_prices=prices,
        new_prices=new_prices,
        factor=factor
    )
    
    return new_prices
```

**Why GPT loves this:**
1. Contract is CLEAR about what's required
2. Types are PRECISE
3. Docstring idea is OBVIOUS
4. Code almost writes itself to satisfy contract

---

## 5. Type Annotations (Always Required)

**Python (PEP 484):**

```python
from typing import List, Dict, Optional, Callable, Tuple
from decimal import Decimal
from dataclasses import dataclass

# Basic types
def process_items(items: List[float]) -> List[float]:
    pass

# Optional (can be None)
def get_user_by_id(user_id: int) -> Optional[User]:
    pass

# Union (one of several types)
def parse_value(value: Union[str, int, float]) -> float:
    pass

# Callable (function parameter)
def apply_to_all(items: List[int], func: Callable[[int], int]) -> List[int]:
    pass

# Custom types with dataclass
@dataclass
class OperationContext:
    operator_id: str
    timestamp: datetime
    request_id: str

# Async functions ALWAYS specify return type with Awaitable/coroutine
async def fetch_data(url: str) -> List[Dict]:
    pass
```

---

## 6. Code Quality Checklist (Contract Verification)

Before submitting code, verify contract satisfaction:

- [ ] **Contract above function** - Is contract docstring present?
- [ ] **All parameters described** - Does contract list all params with types/constraints?
- [ ] **Return type declared** - What type is returned? What are guarantees?
- [ ] **Exceptions documented** - Does contract list all Raises?
- [ ] **Guarantees stated** - What's always true after execution?
- [ ] **Docstring algorithm** - Is algorithm 1-2 sentences, not step-by-step?
- [ ] **Type hints complete** - All params and return have types?
- [ ] **Validation first** - Does code validate contract assumptions?
- [ ] **Happy path obvious** - Is main logic clear after validation?
- [ ] **Error messages specific** - Do exceptions include context?
- [ ] **Async where needed** - All I/O using async/await?

---

## 7. AI-Friendly Patterns

### Pattern 1: Guard Clauses (Fail Fast)

```python
async def process_order(order: Order, user: User) -> ProcessResult:
    """
    Validate order and user, then charge card and ship items.
    """
    
    # Guard clauses (from contract validation)
    if not order:
        raise ValueError("Order required")
    
    if not user:
        raise ValueError("User required")
    
    if user.balance < order.total:
        raise ValueError(f"Insufficient funds: {user.balance} < {order.total}")
    
    if not order.items:
        raise ValueError("Order must contain items")
    
    # Now we know everything is valid, algorithm is obvious
    result = ProcessResult()
    
    # Process safely
    await charge_card(user, order.total)
    await ship_items(order)
    result.success = True
    
    return result
```

### Pattern 2: Context Objects (Not Globals)

```python
async def calculate_price(
    base_price: Decimal,
    context: PricingContext  # Replaces global state
) -> Decimal:
    """
    Apply user-specific discounts and taxes to base price.
    Uses context instead of global variables for testability.
    """
    
    # All pricing rules are in context, not hidden globals
    discounted = base_price * (1 - context.user_discount_percent)
    taxed = discounted * (1 + context.tax_rate)
    
    return taxed.quantize(Decimal("0.01"))
```

### Pattern 3: Type-Driven (Let Types Guide You)

```python
from typing import Protocol

# Define what a "handler" must do (contract)
class MessageHandler(Protocol):
    async def handle(self, msg: Message, ctx: Context) -> Response:
        """Process message, return response."""
        ...

# Implementation details don't matter, contract is clear
async def route_message(
    msg: Message,
    handlers: Dict[str, MessageHandler],
    ctx: Context
) -> Response:
    """
    Find handler for message type, invoke it with context.
    Handler contract guarantees it returns valid Response.
    """
    handler = handlers[msg.type]
    return await handler.handle(msg, ctx)
```

---

## 8. Wildberries + Telegram Bot Example

### Domain: Pricing (Complex, needs contract)

```python
"""
GOAL: Calculate final price for customer including market rates, 
      user discounts, and regional taxes without revealing calculation to user.

PARAMETERS:
  base_price: Decimal - SKU price from Wildberries - >= 0.01
  wildberries_multiplier: Decimal - Market rate (1.0 to 2.0) - From API
  user_discount_percent: float - Customer loyalty discount - 0 to 100
  region_tax_rate: float - Regional tax - 0 to 0.20
  currency: str - "RUB" or "USD" - Affects precision

RETURNS:
  PriceResult - Contains final_price, breakdown (for admin), discount_applied
              - final_price always >= base_price * 0.5 (no negative margin)

RAISES:
  ValueError: If base_price < 0.01
  ValueError: If wildberries_multiplier outside [1.0, 2.0]
  ValueError: If user_discount_percent outside [0, 100]
  CurrencyError: If currency not supported

GUARANTEES:
  - Final price rounded to 2 decimal places
  - Customer never sees internal calculations
  - Breakdown logged with operator_id for audit
  - Function idempotent (same inputs = same output)
  - Pricing change prevents order if > 5% difference
"""
async def calculate_customer_price(
    base_price: Decimal,
    wildberries_multiplier: Decimal,
    user_discount_percent: float,
    region_tax_rate: float,
    currency: str = "RUB"
) -> PriceResult:
    """
    Apply multiplier and discount, then tax, clamping to margin boundaries.
    Return customer-visible price + admin breakdown for auditing.
    """
    
    # Validation
    if base_price < Decimal("0.01"):
        raise ValueError(f"Base price {base_price} too low")
    
    if not (Decimal("1.0") <= wildberries_multiplier <= Decimal("2.0")):
        raise ValueError(f"Multiplier {wildberries_multiplier} outside [1.0, 2.0]")
    
    if not (0 <= user_discount_percent <= 100):
        raise ValueError(f"Discount {user_discount_percent} outside [0, 100]")
    
    # Algorithm
    after_multiplier = base_price * wildberries_multiplier
    discounted = after_multiplier * (1 - Decimal(str(user_discount_percent / 100)))
    taxed = discounted * (1 + Decimal(str(region_tax_rate)))
    
    final_price = taxed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    # Minimum margin
    min_price = base_price * Decimal("0.5")
    if final_price < min_price:
        final_price = min_price
    
    # Build result
    return PriceResult(
        final_price=final_price,
        breakdown={
            "base": base_price,
            "after_wb_multiplier": after_multiplier,
            "after_discount": discounted,
            "final_with_tax": final_price
        },
        discount_applied=user_discount_percent
    )
```

### Domain: Telegram Handler (Simple, contract is brief)

```python
"""
GOAL: Respond to /price command with current pricing for requested product.

PARAMETERS:
  message: Message - Telegram message with product_id in text - Not None
  db: AsyncSession - Database connection - Must be open

RETURNS:
  MessageResponse - User-friendly message or error - Never None

RAISES:
  ProductNotFound: If product_id doesn't exist
  PermissionError: If user blocked

GUARANTEES:
  - Response sent within 3 seconds
  - Error messages don't expose system details
"""
async def handle_price_command(
    message: Message,
    db: AsyncSession
) -> MessageResponse:
    """
    Extract product_id from message, fetch price, return formatted response.
    """
    try:
        product_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        return MessageResponse(
            text="❌ Usage: /price <product_id>",
            chat_id=message.chat.id
        )
    
    product = await db.get_product(product_id)
    if not product:
        return MessageResponse(
            text=f"❌ Product {product_id} not found",
            chat_id=message.chat.id
        )
    
    return MessageResponse(
        text=f"💰 Price for {product.name}: {product.current_price} RUB",
        chat_id=message.chat.id
    )
```

---

## 9. Project Structure with Contracts

```
telegram-bot-project/
├── AGENTS.md                           # This file
├── src/
│   ├── pricing/
│   │   ├── calculator.py               # apply_seasonal_markup (with contract)
│   │   ├── validator.py                # validate_price (with contract)
│   │   └── models.py                   # @dataclass Price, etc
│   ├── inventory/
│   │   ├── sync.py                     # sync_inventory_from_api (with contract)
│   │   └── repository.py               # Database access (with contracts)
│   ├── telegram/
│   │   ├── handlers.py                 # handle_price_command (with contract)
│   │   └── auth.py                     # check_permission (with contract)
│   └── audit/
│       └── logger.py                   # audit_log (with contract)
├── tests/
│   ├── test_pricing.py                 # Test contract satisfaction
│   ├── test_inventory.py
│   └── test_telegram.py
└── docs/
    ├── structure.md                    # Architecture overview
    ├── tech.md                         # Stack: Python 3.11+, asyncio, asyncpg
    └── testing.md                      # Test patterns
```

---

## 10. Development Workflow

### Step 1: Write Contract (Before Code)

```python
"""
GOAL: Fetch inventory from Wildberries, update local cache.

PARAMETERS:
  product_id: int - SKU ID - > 0
  cache: CacheStore - Existing cache layer - Not None

RETURNS:
  Inventory - Current inventory state - Never None

RAISES:
  APIError: If Wildberries unreachable
  CacheError: If cache write fails

GUARANTEES:
  - Cache is updated atomically (all-or-nothing)
  - Old inventory remains if new fetch fails
  - Result reflects API state at call time (not stale)
"""
async def fetch_inventory(product_id: int, cache: CacheStore) -> Inventory:
    # Not implemented yet
    pass
```

### Step 2: Ask GPT to Implement

```
I have this contract:

[paste contract + type hints]

Implement this function following the contract. 
Use asyncio and proper error handling.
```

**GPT generates code that:**
- Satisfies contract
- Has proper error handling
- Uses async/await correctly
- Includes sensible defaults

### Step 3: Verify Contract

```bash
# Does code satisfy contract?
pytest tests/test_inventory.py -v

# Is code typed?
mypy src/ --strict

# Is docstring present and readable?
grep -A 2 "async def fetch_inventory"
```

---

## 11. Commands Reference

```bash
# Type check (contract enforcement)
mypy src/ --strict

# Format code
black src/ tests/

# Lint
pylint src/

# Test contract satisfaction
pytest tests/ -v --cov=src/

# Before commit
black . && mypy . --strict && pytest tests/ -q
```

---

## 12. Key Principles

1. **Contract > Code** – Contract defines truth, code satisfies it
2. **Type Safety** – Types are contracts in themselves (PEP 484)
3. **Algorithm Brief** – 1-2 sentences, not step-by-step
4. **Fail Fast** – Guard clauses validate contract assumptions
5. **No Globals** – Pass context, don't hide state
6. **Async First** – All I/O is async/await
7. **Auditable** – Pricing, inventory, permissions logged
8. **Testable** – Contract makes tests obvious

---

## 13. AI Integration Strategy

### For GitHub Copilot (Auto-complete)

```python
# Write contract above
"""
GOAL: Fetch current price from cache or API.
...
"""
async def get_current_price(product_id: int) -> Decimal:
    # Type Copilot here, it completes to satisfy contract
```

### For Claude/GPT-4 (Chat)

```
I have this contract for pricing calculation:

[PASTE CONTRACT]

Implement following this contract exactly. 
Use Decimal for precision, asyncio for I/O, proper error handling.
```

### For Cline (Autonomous Agent)

```
Reading AGENTS.md...
- Contract-based approach ✓
- Python dataclasses for types ✓
- Async/await required ✓
- Error handling from contract ✓

Now analyzing task: "Implement seasonal pricing"
- Contract found: apply_seasonal_markup ✓
- Parameters: prices, factor, context ✓
- Returns: List[Decimal] ✓
- Guarantees: idempotent, audit logged ✓

Generating code to satisfy contract...
```

---

## Summary

**Contract-based Python development:**

1. **BEFORE code:** Write detailed contract as docstring ABOVE function
2. **IN docstring:** Brief algorithm (1-2 sentences), not steps
3. **TYPE HINTS:** Complete type annotations on all params/returns
4. **CODE:** Guard clauses first, then obvious algorithm
5. **RESULT:** AI generates code that satisfies contract

**GPT reads contract → understands intent → generates obvious code**

This is "casual magic" for AI: the contract makes implementation obvious.

---

**Version:** 1.0  
**Approach:** Contract-based + Type-driven  
**Status:** Ready for production use  
**For:** Cline, Claude, ChatGPT, Codex, GitHub Copilot