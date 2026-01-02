"""MCP Tool definitions for ProofPack.

Each tool corresponds to a ProofPack capability exposed to MCP clients.
Tools follow the MCP tool specification with name, description, and parameters.
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.receipt import dual_hash, emit_receipt


@dataclass
class ToolParameter:
    """A tool parameter definition."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """An MCP tool definition."""
    name: str
    description: str
    parameters: list[ToolParameter]
    handler: Callable


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    receipt_id: Optional[str] = None


# ============================================================================
# Tool Handlers
# ============================================================================

def handle_query_receipts(
    time_range: dict = None,
    receipt_type: str = None,
    payload_filter: dict = None,
    limit: int = 100,
    tenant_id: str = "default",
) -> ToolResult:
    """Search receipt ledger by criteria.

    Args:
        time_range: {"start": ISO8601, "end": ISO8601}
        receipt_type: Filter by receipt type
        payload_filter: Key-value filters on payload
        limit: Maximum results to return
        tenant_id: Tenant identifier

    Returns:
        ToolResult with list of matching receipts
    """
    try:
        from ledger import query_receipts

        def predicate(r: dict) -> bool:
            # Type filter
            if receipt_type and r.get("receipt_type") != receipt_type:
                return False

            # Time range filter
            if time_range:
                ts = r.get("ts", "")
                if time_range.get("start") and ts < time_range["start"]:
                    return False
                if time_range.get("end") and ts > time_range["end"]:
                    return False

            # Payload filter
            if payload_filter:
                for key, value in payload_filter.items():
                    if r.get(key) != value:
                        return False

            return True

        receipts = query_receipts(predicate, tenant_id=tenant_id)

        # Apply limit
        receipts = receipts[:limit]

        receipt = emit_receipt("mcp_query", {
            "tool": "query_receipts",
            "results_count": len(receipts),
            "filters": {
                "time_range": time_range,
                "receipt_type": receipt_type,
                "payload_filter": payload_filter,
            },
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={"receipts": receipts, "count": len(receipts)},
            receipt_id=receipt.get("payload_hash"),
        )

    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_validate_receipt(
    receipt_id: str,
    tenant_id: str = "default",
) -> ToolResult:
    """Verify dual-hash integrity of a receipt.

    Args:
        receipt_id: The payload_hash of the receipt to validate
        tenant_id: Tenant identifier

    Returns:
        ToolResult with validation status and integrity info
    """
    try:
        from ledger import query_receipts

        # Find receipt by ID
        receipts = query_receipts(
            lambda r: r.get("payload_hash", "").startswith(receipt_id[:16]),
            tenant_id=tenant_id
        )

        if not receipts:
            return ToolResult(
                success=False,
                data=None,
                error=f"Receipt not found: {receipt_id}"
            )

        receipt_data = receipts[0]

        # Recompute hash to verify integrity
        payload = {k: v for k, v in receipt_data.items()
                   if k not in ("receipt_type", "ts", "tenant_id", "payload_hash")}
        computed_hash = dual_hash(json.dumps(payload, sort_keys=True))

        # Split hashes to check each component
        stored_parts = receipt_data.get("payload_hash", "").split(":")
        computed_parts = computed_hash.split(":")

        sha256_valid = len(stored_parts) >= 1 and len(computed_parts) >= 1 and \
                       stored_parts[0] == computed_parts[0]
        blake3_valid = len(stored_parts) >= 2 and len(computed_parts) >= 2 and \
                       stored_parts[1] == computed_parts[1]

        is_valid = sha256_valid and blake3_valid

        validation_receipt = emit_receipt("mcp_validate", {
            "tool": "validate_receipt",
            "receipt_id": receipt_id,
            "is_valid": is_valid,
            "sha256_valid": sha256_valid,
            "blake3_valid": blake3_valid,
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={
                "is_valid": is_valid,
                "sha256_valid": sha256_valid,
                "blake3_valid": blake3_valid,
                "receipt_type": receipt_data.get("receipt_type"),
                "ts": receipt_data.get("ts"),
            },
            receipt_id=validation_receipt.get("payload_hash"),
        )

    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_get_lineage(
    receipt_id: str,
    depth: int = 10,
    tenant_id: str = "default",
) -> ToolResult:
    """Trace receipt ancestry.

    Args:
        receipt_id: Starting receipt ID
        depth: Maximum depth to trace
        tenant_id: Tenant identifier

    Returns:
        ToolResult with lineage tree
    """
    try:
        from ledger import query_receipts

        lineage = []
        current_id = receipt_id
        visited = set()

        for _ in range(depth):
            if current_id in visited:
                break
            visited.add(current_id)

            receipts = query_receipts(
                lambda r, cid=current_id: r.get("payload_hash", "").startswith(cid[:16]),
                tenant_id=tenant_id
            )

            if not receipts:
                break

            receipt = receipts[0]
            lineage.append({
                "receipt_id": receipt.get("payload_hash"),
                "type": receipt.get("receipt_type"),
                "ts": receipt.get("ts"),
            })

            # Look for parent reference
            parent_id = receipt.get("parent_receipt_id") or \
                       receipt.get("parent_agent_id") or \
                       receipt.get("source_receipt")

            if not parent_id:
                break

            current_id = parent_id

        emit_receipt("mcp_lineage", {
            "tool": "get_lineage",
            "receipt_id": receipt_id,
            "depth_traced": len(lineage),
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={"lineage": lineage, "depth": len(lineage)},
        )

    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_spawn_helper(
    problem_description: str,
    context: dict = None,
    tenant_id: str = "default",
) -> ToolResult:
    """Trigger RED gate helper spawning via MCP.

    This tool allows external clients to spawn helper agents when they
    encounter problems. Same gate rules and limits apply.

    Args:
        problem_description: Description of the problem to solve
        context: Additional context for helpers
        tenant_id: Tenant identifier

    Returns:
        ToolResult with spawn receipt and agent IDs
    """
    try:
        from spawner.birth import spawn_for_gate

        # Calculate confidence from problem (mock - real would analyze problem)
        context = context or {}
        base_confidence = context.get("confidence", 0.5)

        # MCP-triggered spawns always go through RED gate
        result, spawn_receipt = spawn_for_gate(
            gate_color="RED",
            confidence_score=base_confidence,
            wound_count=context.get("wound_count", 0),
            variance=context.get("variance", 0.0),
            parent_agent_id=None,
            tenant_id=tenant_id,
        )

        if not result:
            return ToolResult(
                success=False,
                data=None,
                error="Spawning disabled or at capacity"
            )

        # Emit receipt for MCP-triggered spawn
        mcp_receipt = emit_receipt("mcp_spawn", {
            "tool": "spawn_helper",
            "trigger_source": "MCP_CLIENT",
            "problem_description": problem_description[:500],  # Truncate
            "agent_ids": result.agent_ids,
            "spawn_count": result.spawn_count,
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={
                "agent_ids": result.agent_ids,
                "spawn_count": result.spawn_count,
                "group_id": result.group_id,
                "trigger": "MCP_CLIENT",
            },
            receipt_id=mcp_receipt.get("payload_hash"),
        )

    except ImportError as e:
        return ToolResult(
            success=False,
            data=None,
            error=f"Spawner module not available: {e}"
        )
    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_check_confidence(
    action_proposal: dict,
    tenant_id: str = "default",
) -> ToolResult:
    """Run gate check without execution.

    Preview what gate decision would be made and what agents would spawn.

    Args:
        action_proposal: Description of proposed action
        tenant_id: Tenant identifier

    Returns:
        ToolResult with gate color, confidence, and spawn preview
    """
    try:
        from gate.decision import get_spawn_preview
        from constants import GATE_GREEN_THRESHOLD, GATE_YELLOW_THRESHOLD

        # Extract confidence from proposal
        confidence = action_proposal.get("confidence", 0.5)
        wound_count = action_proposal.get("wound_count", 0)
        variance = action_proposal.get("variance", 0.0)

        # Determine gate color
        if confidence >= GATE_GREEN_THRESHOLD:
            gate_color = "GREEN"
        elif confidence >= GATE_YELLOW_THRESHOLD:
            gate_color = "YELLOW"
        else:
            gate_color = "RED"

        # Get spawn preview
        spawn_preview = get_spawn_preview(confidence, wound_count, variance)

        emit_receipt("mcp_check_confidence", {
            "tool": "check_confidence",
            "confidence": confidence,
            "gate_color": gate_color,
            "would_spawn": spawn_preview.get("would_spawn", 0),
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={
                "gate_color": gate_color,
                "confidence_score": confidence,
                "would_spawn": spawn_preview.get("would_spawn", 0),
                "spawn_preview": spawn_preview,
            },
        )

    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_list_patterns(
    domain_filter: str = None,
    tenant_id: str = "default",
) -> ToolResult:
    """Get graduated helper patterns.

    Args:
        domain_filter: Optional filter by domain
        tenant_id: Tenant identifier

    Returns:
        ToolResult with list of patterns
    """
    try:
        from spawner.patterns import get_all_patterns

        patterns = get_all_patterns(tenant_id=tenant_id)

        # Apply domain filter
        if domain_filter:
            patterns = [
                p for p in patterns
                if domain_filter.lower() in p.get("domain", "").lower()
            ]

        emit_receipt("mcp_list_patterns", {
            "tool": "list_patterns",
            "pattern_count": len(patterns),
            "domain_filter": domain_filter,
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={"patterns": patterns, "count": len(patterns)},
        )

    except ImportError:
        return ToolResult(
            success=True,
            data={"patterns": [], "count": 0},
        )
    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


def handle_agent_status(tenant_id: str = "default") -> ToolResult:
    """Get current spawned agent status.

    Returns:
        ToolResult with active agents, depths, TTLs
    """
    try:
        from spawner.registry import get_active_agents, get_population_count, MAX_AGENTS

        agents = get_active_agents()
        population = get_population_count()

        agent_data = []
        for agent in agents:
            remaining_ttl = max(0, agent.ttl_seconds - (time.time() - agent.spawned_at))
            agent_data.append({
                "agent_id": agent.agent_id,
                "type": agent.agent_type.value,
                "state": agent.state.value,
                "depth": agent.depth,
                "remaining_ttl_seconds": int(remaining_ttl),
                "gate_color": agent.gate_color,
            })

        emit_receipt("mcp_agent_status", {
            "tool": "agent_status",
            "active_count": population,
            "max_population": MAX_AGENTS,
            "tenant_id": tenant_id,
        })

        return ToolResult(
            success=True,
            data={
                "active_agents": agent_data,
                "population": population,
                "max_population": MAX_AGENTS,
                "capacity_remaining": MAX_AGENTS - population,
            },
        )

    except ImportError:
        return ToolResult(
            success=True,
            data={
                "active_agents": [],
                "population": 0,
                "max_population": 50,
                "capacity_remaining": 50,
            },
        )
    except Exception as e:
        return ToolResult(success=False, data=None, error=str(e))


# ============================================================================
# Tool Registry
# ============================================================================

TOOLS: dict[str, ToolDefinition] = {
    "query_receipts": ToolDefinition(
        name="query_receipts",
        description="Search receipt ledger by criteria including time range, receipt type, and payload filters",
        parameters=[
            ToolParameter("time_range", "object", "Time range with start/end ISO8601 timestamps", required=False),
            ToolParameter("receipt_type", "string", "Filter by receipt type", required=False),
            ToolParameter("payload_filter", "object", "Key-value filters on payload", required=False),
            ToolParameter("limit", "number", "Maximum results to return (default 100)", required=False, default=100),
        ],
        handler=handle_query_receipts,
    ),
    "validate_receipt": ToolDefinition(
        name="validate_receipt",
        description="Verify dual-hash integrity of a receipt",
        parameters=[
            ToolParameter("receipt_id", "string", "The payload_hash of the receipt to validate"),
        ],
        handler=handle_validate_receipt,
    ),
    "get_lineage": ToolDefinition(
        name="get_lineage",
        description="Trace receipt ancestry to find parent receipts",
        parameters=[
            ToolParameter("receipt_id", "string", "Starting receipt ID"),
            ToolParameter("depth", "number", "Maximum depth to trace (default 10)", required=False, default=10),
        ],
        handler=handle_get_lineage,
    ),
    "spawn_helper": ToolDefinition(
        name="spawn_helper",
        description="Trigger RED gate helper spawning for problem solving",
        parameters=[
            ToolParameter("problem_description", "string", "Description of the problem to solve"),
            ToolParameter("context", "object", "Additional context for helpers", required=False),
        ],
        handler=handle_spawn_helper,
    ),
    "check_confidence": ToolDefinition(
        name="check_confidence",
        description="Run gate check without execution to preview decision",
        parameters=[
            ToolParameter("action_proposal", "object", "Description of proposed action with confidence score"),
        ],
        handler=handle_check_confidence,
    ),
    "list_patterns": ToolDefinition(
        name="list_patterns",
        description="Get graduated helper patterns from successful agents",
        parameters=[
            ToolParameter("domain_filter", "string", "Filter patterns by domain", required=False),
        ],
        handler=handle_list_patterns,
    ),
    "agent_status": ToolDefinition(
        name="agent_status",
        description="Get current spawned agent status including counts, depths, and TTLs",
        parameters=[],
        handler=handle_agent_status,
    ),
}


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Get tool definition by name."""
    return TOOLS.get(name)


def list_tools() -> list[dict]:
    """List all available tools in MCP format."""
    tools = []
    for tool in TOOLS.values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    p.name: {
                        "type": p.type,
                        "description": p.description,
                    }
                    for p in tool.parameters
                },
                "required": [p.name for p in tool.parameters if p.required],
            },
        })
    return tools


def execute_tool(
    name: str,
    arguments: dict,
    tenant_id: str = "default",
) -> ToolResult:
    """Execute a tool by name with arguments.

    Args:
        name: Tool name
        arguments: Tool arguments
        tenant_id: Tenant identifier

    Returns:
        ToolResult from tool execution
    """
    tool = get_tool(name)
    if not tool:
        return ToolResult(
            success=False,
            data=None,
            error=f"Unknown tool: {name}"
        )

    try:
        # Add tenant_id to arguments
        arguments["tenant_id"] = tenant_id

        # Filter arguments to only those accepted by handler
        import inspect
        sig = inspect.signature(tool.handler)
        valid_args = {
            k: v for k, v in arguments.items()
            if k in sig.parameters
        }

        return tool.handler(**valid_args)

    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            error=f"Tool execution error: {e}"
        )
