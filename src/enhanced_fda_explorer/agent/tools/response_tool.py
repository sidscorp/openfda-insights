"""
Response Tool for Agent-Controlled Display.
Forces the agent to structure its final response and explicitly select artifacts.
"""
from typing import Optional, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class RespondToUserInput(BaseModel):
    answer: str = Field(description="The final text response to the user (markdown supported).")
    artifact_ids_to_display: List[str] = Field(
        default_factory=list,
        description="The list of Data Artifact IDs (e.g. 'art-123') that are relevant to this answer and should be displayed in the UI."
    )


class RespondToUserTool(BaseTool):
    name: str = "respond_to_user"
    description: str = "Use this tool to deliver the final answer to the user and select which data tables/charts to show."
    args_schema: type[BaseModel] = RespondToUserInput

    def _run(self, answer: str, artifact_ids_to_display: List[str]) -> str:
        # This tool doesn't 'do' anything in the traditional sense; 
        # its invocation is the signal that the agent is done.
        # The system intercepts this call.
        return f"Response delivered: {answer[:50]}..."
    
    async def _arun(self, answer: str, artifact_ids_to_display: List[str]) -> str:
        return self._run(answer, artifact_ids_to_display)
