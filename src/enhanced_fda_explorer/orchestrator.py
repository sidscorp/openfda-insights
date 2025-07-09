"""
Conversational Orchestrator for Enhanced FDA Explorer
Implementation using OpenAI Function Calling (recommended from P1-T018 evaluation)
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import openai

from .core import FDAExplorer
from .config import get_config


@dataclass
class OrchestrationResult:
    """Result of orchestrating an FDA query"""
    user_query: str
    understanding: Dict[str, Any]
    tool_calls: List[Dict[str, Any]]
    results: Dict[str, Any]
    synthesis: str
    execution_time: float
    metadata: Dict[str, Any]


class FDAOrchestrator:
    """
    Conversational orchestrator for Enhanced FDA Explorer
    
    Interprets natural language queries about medical devices and intelligently
    orchestrates calls across multiple FDA databases to provide comprehensive answers.
    """
    
    def __init__(self, config=None):
        """Initialize the orchestrator"""
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.fda_explorer = FDAExplorer(self.config)
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if self.config.ai.api_key and self.config.ai.provider == "openai":
            self.openai_client = openai.OpenAI(api_key=self.config.ai.api_key)
        
        # Define FDA tools for function calling
        self.fda_tools = self._define_fda_tools()
        
        # System prompt for the orchestrator
        self.system_prompt = self._create_system_prompt()
    
    def _define_fda_tools(self) -> List[Dict[str, Any]]:
        """Define FDA tools for OpenAI function calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_fda_data",
                    "description": "Search FDA medical device databases for adverse events, recalls, approvals, and classifications",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for the medical device or manufacturer"
                            },
                            "query_type": {
                                "type": "string",
                                "enum": ["device", "manufacturer"],
                                "description": "Type of search query"
                            },
                            "endpoints": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["event", "recall", "510k", "pma", "classification", "udi"]
                                },
                                "description": "Specific FDA endpoints to search"
                            },
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1000,
                                "default": 100,
                                "description": "Maximum number of results per endpoint"
                            }
                        },
                        "required": ["query", "query_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_device_intelligence",
                    "description": "Get comprehensive intelligence analysis for a specific medical device",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_name": {
                                "type": "string",
                                "description": "Name of the medical device to analyze"
                            },
                            "lookback_months": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                                "default": 12,
                                "description": "Number of months to look back for analysis"
                            },
                            "include_risk_assessment": {
                                "type": "boolean",
                                "default": True,
                                "description": "Whether to include AI-powered risk assessment"
                            }
                        },
                        "required": ["device_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_devices",
                    "description": "Compare multiple medical devices side-by-side for safety and regulatory metrics",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "description": "List of device names to compare"
                            },
                            "lookback_months": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                                "default": 12,
                                "description": "Number of months to look back for comparison"
                            }
                        },
                        "required": ["device_names"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_manufacturer_intelligence",
                    "description": "Analyze manufacturer safety profile and regulatory compliance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manufacturer_name": {
                                "type": "string",
                                "description": "Name of the manufacturer to analyze"
                            },
                            "lookback_months": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                                "default": 12,
                                "description": "Number of months to look back for analysis"
                            }
                        },
                        "required": ["manufacturer_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trend_analysis",
                    "description": "Analyze trends in medical device safety and regulatory data over time",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Device or topic to analyze trends for"
                            },
                            "time_periods": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["3months", "6months", "1year", "2years", "3years"]
                                },
                                "description": "Time periods for trend analysis"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for the orchestrator"""
        return """You are an expert FDA medical device data analyst and orchestrator for Enhanced FDA Explorer. Your role is to:

1. **Understand User Intent**: Interpret natural language queries about medical devices, manufacturers, safety issues, and regulatory matters.

2. **Plan Data Collection**: Determine which FDA databases and analysis methods are needed to answer the user's question comprehensively.

3. **Execute Orchestrated Searches**: Use available tools to gather relevant data from FDA databases including:
   - Adverse event reports (MAUDE)
   - Device recalls
   - 510(k) premarket notifications  
   - PMA premarket approvals
   - Device classifications
   - Unique device identifiers (UDI)

4. **Synthesize Results**: Combine and analyze data from multiple sources to provide comprehensive, accurate, and actionable insights.

5. **Communicate Clearly**: Present findings in clear, professional language appropriate for policy scientists and regulatory analysts.

**Key Guidelines:**
- Always prioritize accuracy and cite data sources
- Acknowledge limitations and uncertainties in the data
- Provide context about FDA processes and regulatory significance
- Use multiple data sources when possible for comprehensive analysis
- Flag any potential safety concerns clearly
- Maintain objectivity and avoid making medical recommendations

**Available Tools:**
- search_fda_data: Search across FDA databases
- get_device_intelligence: Comprehensive device analysis
- compare_devices: Side-by-side device comparison
- get_manufacturer_intelligence: Manufacturer safety profile
- get_trend_analysis: Temporal trend analysis

Use these tools strategically to provide the most complete and accurate response to the user's query."""
    
    async def process_query(self, user_query: str, conversation_history: List[Dict[str, str]] = None) -> OrchestrationResult:
        """
        Process a natural language query about FDA medical device data
        
        Args:
            user_query: Natural language query from the user
            conversation_history: Optional previous conversation context
            
        Returns:
            OrchestrationResult with complete analysis
        """
        start_time = datetime.now()
        
        try:
            # Build conversation messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user query
            messages.append({"role": "user", "content": user_query})
            
            # Call OpenAI with function calling
            if not self.openai_client:
                raise ValueError("OpenAI client not configured. Please set AI_API_KEY and AI_PROVIDER=openai")
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.config.ai.model,
                    messages=messages,
                    tools=self.fda_tools,
                    tool_choice="auto",
                    temperature=self.config.ai.temperature,
                    max_tokens=self.config.ai.max_tokens
                )
            )
            
            # Process response and execute tool calls
            tool_calls = []
            results = {}
            
            if response.choices[0].message.tool_calls:
                # Execute each tool call
                for tool_call in response.choices[0].message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    self.logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                    
                    # Execute the FDA tool
                    tool_result = await self._execute_fda_tool(tool_name, tool_args)
                    
                    tool_calls.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result_summary": self._summarize_tool_result(tool_result)
                    })
                    
                    results[tool_name] = tool_result
                
                # Generate synthesis with tool results
                synthesis = await self._synthesize_results(user_query, tool_calls, results, response.choices[0].message.content)
            else:
                # Direct response without tool calls
                synthesis = response.choices[0].message.content
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return OrchestrationResult(
                user_query=user_query,
                understanding=self._extract_understanding(user_query, tool_calls),
                tool_calls=tool_calls,
                results=results,
                synthesis=synthesis,
                execution_time=execution_time,
                metadata={
                    "model_used": self.config.ai.model,
                    "total_tool_calls": len(tool_calls),
                    "timestamp": start_time.isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Orchestration failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return OrchestrationResult(
                user_query=user_query,
                understanding={"error": str(e)},
                tool_calls=[],
                results={},
                synthesis=f"I apologize, but I encountered an error while processing your query: {str(e)}. Please try rephrasing your question or contact support if the issue persists.",
                execution_time=execution_time,
                metadata={"error": True, "timestamp": start_time.isoformat()}
            )
    
    async def _execute_fda_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Execute an FDA tool with the given arguments"""
        try:
            if tool_name == "search_fda_data":
                return await self.fda_explorer.search(
                    query=tool_args["query"],
                    query_type=tool_args.get("query_type", "device"),
                    endpoints=tool_args.get("endpoints"),
                    limit=tool_args.get("limit", 100),
                    include_ai_analysis=False  # Avoid nested AI calls
                )
            
            elif tool_name == "get_device_intelligence":
                return await self.fda_explorer.get_device_intelligence(
                    device_name=tool_args["device_name"],
                    lookback_months=tool_args.get("lookback_months", 12),
                    include_risk_assessment=tool_args.get("include_risk_assessment", True)
                )
            
            elif tool_name == "compare_devices":
                return await self.fda_explorer.compare_devices(
                    device_names=tool_args["device_names"],
                    lookback_months=tool_args.get("lookback_months", 12)
                )
            
            elif tool_name == "get_manufacturer_intelligence":
                return await self.fda_explorer.get_manufacturer_intelligence(
                    manufacturer_name=tool_args["manufacturer_name"],
                    lookback_months=tool_args.get("lookback_months", 12)
                )
            
            elif tool_name == "get_trend_analysis":
                return await self.fda_explorer.get_trend_analysis(
                    query=tool_args["query"],
                    time_periods=tool_args.get("time_periods")
                )
            
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            self.logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"error": str(e), "tool": tool_name}
    
    def _summarize_tool_result(self, result: Any) -> str:
        """Create a brief summary of tool result for context"""
        if isinstance(result, dict):
            if "error" in result:
                return f"Error: {result['error']}"
            elif "total_results" in result:
                return f"Found {result['total_results']} results"
            elif "device_name" in result:
                return f"Device analysis for {result['device_name']}"
            elif "devices" in result:
                return f"Comparison of {len(result['devices'])} devices"
            elif "manufacturer_name" in result:
                return f"Manufacturer analysis for {result['manufacturer_name']}"
            elif "trend_data" in result:
                periods = len(result["trend_data"])
                return f"Trend analysis across {periods} time periods"
        
        return "Analysis completed"
    
    async def _synthesize_results(self, user_query: str, tool_calls: List[Dict], results: Dict, initial_response: str) -> str:
        """Synthesize tool results into a comprehensive response"""
        try:
            # Prepare synthesis prompt
            synthesis_messages = [
                {"role": "system", "content": """You are synthesizing FDA medical device data analysis results. 
                Provide a comprehensive, accurate response that:
                1. Directly answers the user's question
                2. Summarizes key findings from the data
                3. Provides relevant context and implications
                4. Acknowledges any limitations or gaps
                5. Uses clear, professional language for policy scientists"""},
                {"role": "user", "content": f"""
                Original Query: {user_query}
                
                Tool Calls Executed: {json.dumps(tool_calls, indent=2)}
                
                Results Summary: {self._create_results_summary(results)}
                
                Please provide a comprehensive synthesis of these findings to answer the user's question.
                """}
            ]
            
            if self.openai_client:
                synthesis_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.openai_client.chat.completions.create(
                        model=self.config.ai.model,
                        messages=synthesis_messages,
                        temperature=0.3,  # Lower temperature for factual synthesis
                        max_tokens=1500
                    )
                )
                return synthesis_response.choices[0].message.content
            else:
                # Fallback without AI synthesis
                return self._create_basic_synthesis(user_query, tool_calls, results)
                
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            return self._create_basic_synthesis(user_query, tool_calls, results)
    
    def _create_results_summary(self, results: Dict) -> str:
        """Create a structured summary of all results"""
        summary_parts = []
        
        for tool_name, result in results.items():
            if isinstance(result, dict):
                if "error" in result:
                    summary_parts.append(f"{tool_name}: Error - {result['error']}")
                elif "total_results" in result:
                    summary_parts.append(f"{tool_name}: {result['total_results']} records found")
                else:
                    summary_parts.append(f"{tool_name}: Analysis completed")
            else:
                summary_parts.append(f"{tool_name}: Data retrieved")
        
        return "\\n".join(summary_parts)
    
    def _create_basic_synthesis(self, user_query: str, tool_calls: List[Dict], results: Dict) -> str:
        """Create basic synthesis without AI when AI synthesis fails"""
        synthesis_parts = [
            f"Based on your query about '{user_query}', I executed {len(tool_calls)} analysis tools:",
            ""
        ]
        
        for tool_call in tool_calls:
            tool_name = tool_call["tool"]
            summary = tool_call["result_summary"]
            synthesis_parts.append(f"• {tool_name.replace('_', ' ').title()}: {summary}")
        
        synthesis_parts.extend([
            "",
            "The analysis has been completed with the available FDA data. ",
            "Please refer to the detailed results for specific findings and recommendations."
        ])
        
        return "\\n".join(synthesis_parts)
    
    def _extract_understanding(self, user_query: str, tool_calls: List[Dict]) -> Dict[str, Any]:
        """Extract understanding of the user's intent from the tool calls made"""
        return {
            "query": user_query,
            "intent_indicators": {
                "search_requested": any("search" in call["tool"] for call in tool_calls),
                "device_analysis": any("device_intelligence" in call["tool"] for call in tool_calls),
                "comparison_requested": any("compare" in call["tool"] for call in tool_calls),
                "manufacturer_focus": any("manufacturer" in call["tool"] for call in tool_calls),
                "trend_analysis": any("trend" in call["tool"] for call in tool_calls)
            },
            "tools_selected": [call["tool"] for call in tool_calls],
            "complexity": "high" if len(tool_calls) > 2 else "medium" if len(tool_calls) > 1 else "low"
        }
    
    async def close(self):
        """Clean up resources"""
        if self.fda_explorer:
            await self.fda_explorer.close()


# Example usage and testing
async def test_orchestrator():
    """Test the orchestrator with sample queries"""
    orchestrator = FDAOrchestrator()
    
    test_queries = [
        "What are the main safety issues with pacemakers?",
        "Compare insulin pumps vs glucose monitors for adverse events",
        "Tell me about Medtronic's recent recalls and regulatory issues",
        "What trends do you see in cardiac device safety over the past 2 years?"
    ]
    
    print("🤖 Testing Enhanced FDA Explorer Orchestrator")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\\n📝 Test Query {i}: {query}")
        print("-" * 40)
        
        try:
            result = await orchestrator.process_query(query)
            
            print(f"🧠 Understanding: {result.understanding['complexity']} complexity")
            print(f"🔧 Tools Used: {len(result.tool_calls)}")
            print(f"⏱️  Execution Time: {result.execution_time:.2f}s")
            print(f"📊 Response Length: {len(result.synthesis)} characters")
            print()
            print("🎯 Synthesis Preview:")
            print(result.synthesis[:200] + "..." if len(result.synthesis) > 200 else result.synthesis)
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
    
    await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(test_orchestrator())