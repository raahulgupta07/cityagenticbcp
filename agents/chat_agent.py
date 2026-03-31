"""
Chat Agent — Tool-calling conversational agent for BCP data queries.
"""
import json
from utils.llm_client import call_llm, is_llm_available
from agents.config import MAX_TURNS, MAX_TOKENS, TEMPERATURE

# Import tools to trigger registration
import agents.tools.data_tools
import agents.tools.model_tools
from agents.tools.registry import get_all_tools, execute_tool

SYSTEM_PROMPT = """You are the AI assistant for City BCP Agent — a Business Continuity Planning system
managing backup generators and fuel supply across 55+ sites in Myanmar, organized into 3 sectors:
CP (City Pharmacy, 25 sites), CMHL (City Mart Holdings, 30 sites), and CFC (City Food Chain, 2 factories).

You have access to tools that can:
- Query sites, generators, daily operations, and fuel prices from the database
- Get buffer status (days of fuel remaining per site)
- Get sector-level summary KPIs
- Forecast fuel prices (7-day predictions)
- Predict stockout dates (when sites will run out of fuel)
- Check generator efficiency and detect anomalies
- Compute BCP scores (0-100, grades A-F) per site
- Predict blackout probability
- Run custom SQL queries

RULES:
1. When asked a question, decide if you need tools. DO use tools — don't guess data values.
2. Use specific numbers from tool results in your answers.
3. Be concise (max 200 words unless asked for detail).
4. If multiple tools are needed, call them one at a time.
5. Always end with a recommendation or actionable insight when appropriate.
6. Fuel prices are in MMK (Myanmar Kyat) per liter.
7. Buffer days = spare_tank_balance / daily_consumption. Below 3 = critical, below 7 = warning.
8. BCP grades: A (80-100) = resilient, B (60-79) = adequate, C (40-59) = at risk, D (20-39) = vulnerable, F (0-19) = critical.

EXAMPLE QUESTIONS AND TOOL ROUTING:
- "Which sites are running low?" → get_buffer_status with max_days=7
- "Compare Denko vs Moon Sun" → query_fuel_prices
- "What will diesel cost next week?" → forecast_fuel_price
- "Is CM19 efficient?" → check_efficiency with site_id=CM19
- "BCP scores for CMHL" → compute_bcp_scores with sector_id=CMHL
"""


def chat(user_message, conversation_history=None):
    """
    Process a user message through the agent.

    Args:
        user_message: str
        conversation_history: list of {"role": "user"|"assistant", "content": str}

    Returns:
        {"response": str, "tool_calls": list, "error": str or None}
    """
    if not is_llm_available():
        return _rule_based_response(user_message)

    schemas, _ = get_all_tools()

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    tool_calls_made = []

    for turn in range(MAX_TURNS):
        result = call_llm(messages, tools=schemas, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)

        if "error" in result:
            return {"response": None, "tool_calls": tool_calls_made, "error": result["error"]}

        try:
            msg = result["choices"][0]["message"]
        except (KeyError, IndexError):
            return {"response": None, "tool_calls": tool_calls_made, "error": "Unexpected LLM response"}

        # Check for tool calls
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            # Final text response
            return {
                "response": msg.get("content", ""),
                "tool_calls": tool_calls_made,
                "error": None,
            }

        # Execute tools
        messages.append(msg)  # Add assistant message with tool_calls

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool_args = func.get("arguments", "{}")

            tool_result = execute_tool(tool_name, tool_args)
            tool_calls_made.append({"tool": tool_name, "args": tool_args, "result_preview": tool_result[:200]})

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", tool_name),
                "content": tool_result,
            })

    # Max turns reached
    return {
        "response": "I ran out of processing steps. Please try a simpler question.",
        "tool_calls": tool_calls_made,
        "error": None,
    }


def _rule_based_response(user_message):
    """Fallback when no LLM API is available."""
    msg = user_message.lower()

    # Try to answer common questions from DB directly
    from agents.tools.data_tools import get_buffer_status, get_sector_summary

    if any(w in msg for w in ["buffer", "fuel", "running low", "stockout", "critical"]):
        df = get_buffer_status(max_days=7)
        if hasattr(df, 'empty') and not df.empty:
            sites = df.head(5).to_dict(orient="records")
            lines = [f"- {s['site_id']} ({s['sector_id']}): {s.get('days_of_buffer', 'N/A')} days" for s in sites]
            return {
                "response": f"**Sites with low buffer (<7 days):**\n" + "\n".join(lines) +
                           "\n\n*Note: AI features require an API key. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.*",
                "tool_calls": [{"tool": "get_buffer_status", "args": "{}", "result_preview": "rule-based"}],
                "error": None,
            }

    if any(w in msg for w in ["sector", "summary", "overview"]):
        df = get_sector_summary()
        if hasattr(df, 'empty') and not df.empty:
            lines = [f"- {r['sector_id']}: {r['sites']} sites, {r['total_fuel_used_liters']:,.0f}L used, {r['avg_buffer_days']} days buffer"
                     for _, r in df.iterrows()]
            return {
                "response": f"**Sector Summary:**\n" + "\n".join(lines),
                "tool_calls": [{"tool": "get_sector_summary", "args": "{}", "result_preview": "rule-based"}],
                "error": None,
            }

    return {
        "response": "I can help with:\n- Buffer status & stockout risk\n- Fuel prices & forecasts\n- Generator efficiency\n- BCP scores\n- Sector summaries\n\n*Full AI chat requires an API key. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.*",
        "tool_calls": [],
        "error": None,
    }
