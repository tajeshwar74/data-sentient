"""
LangChain utilities for agentic AI integration with data pipeline.
This module provides agent initialization and management for CSV processing,
data transformation, and quality monitoring tasks.
"""

import os
import json
from typing import Any, Dict, List, Optional
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
import pandas as pd
from datetime import datetime


# Initialize LLM
def get_llm(temperature: float = 0.1, model: str = "gpt-4"):
    """Initialize OpenAI LLM for agent operations."""
    return ChatOpenAI(
        temperature=temperature, model=model, api_key=os.getenv("OPENAI_API_KEY")
    )


class CSVAnalysisAgent:
    """
    Agent for CSV file analysis and preprocessing.
    Maintains all core logic while adding agentic decision-making capabilities.
    """

    def __init__(self):
        self.llm = get_llm(temperature=0.1)
        self.tools = self._create_tools()
        self.executor = self._create_executor()

    def _create_tools(self) -> List[Tool]:
        """Define tools for CSV analysis agent."""
        from agent_ingest import analyze_csv_format, normalize_table_name, infer_type

        tools = [
            Tool(
                name="analyze_csv_format",
                func=self._analyze_csv_wrapper,
                description="Analyze CSV file format including delimiter, encoding, and structure. "
                "Returns detected format parameters.",
                args_schema=None,
            ),
            Tool(
                name="normalize_table_name",
                func=self._normalize_table_wrapper,
                description="Normalize file name to database-friendly table name. "
                "Handles special characters and ensures SQL compliance.",
                args_schema=None,
            ),
            Tool(
                name="read_csv_data",
                func=self._read_csv_wrapper,
                description="Read CSV file with auto-detection of optimal parameters. "
                "Returns DataFrame info and statistics.",
                args_schema=None,
            ),
        ]
        return tools

    def _analyze_csv_wrapper(self, file_path: str) -> Dict[str, Any]:
        """Wrapper for CSV analysis."""
        from agent_ingest import analyze_csv_format

        result = analyze_csv_format(file_path)
        return result or {"status": "analysis_failed"}

    def _normalize_table_wrapper(self, file_name: str) -> str:
        """Wrapper for table name normalization."""
        from agent_ingest import normalize_table_name

        return normalize_table_name(file_name)

    def _read_csv_wrapper(self, file_path: str) -> Dict[str, Any]:
        """Wrapper for CSV reading with format detection."""
        from agent_ingest import analyze_csv_format
        import pandas as pd

        csv_format = analyze_csv_format(file_path)

        try:
            if csv_format and csv_format["delimiter"] != ",":
                df = pd.read_csv(file_path, delimiter=csv_format["delimiter"])
            else:
                df = pd.read_csv(file_path)

            return {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist(),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "null_counts": df.isnull().sum().to_dict(),
                "status": "success",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _create_executor(self):
        """Create agent executor with prompt template."""
        system_prompt = """You are an expert data engineer specializing in CSV data processing.
Your role is to analyze and prepare CSV files for database ingestion. You have access to tools for:
1. Analyzing CSV file formats and detecting optimal parsing parameters
2. Normalizing file names to SQL-compliant table names
3. Reading and inspecting CSV data

For each CSV file:
- First analyze the format to detect delimiter and encoding
- Then normalize the table name for SQL compliance
- Finally read the data to get statistics and validate structure

Provide clear recommendations on how to process each file based on your analysis."""

        agent = create_agent(
            model=self.llm, tools=self.tools, system_prompt=system_prompt, debug=True
        )
        return agent

    def analyze_and_prepare_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Agentic analysis and preparation of CSV file.
        Agent decides on processing strategy while maintaining original logic.
        """
        query = f"""Analyze and prepare the CSV file at: {file_path}"

        Please:
        1. Analyze the CSV format (delimiter, encoding, structure)
        2. Recommend a normalized table name
        3. Read the data and provide statistics
        4. Give recommendations for processing this file"""

        try:
            result = self.executor.invoke({"messages": [{"user", query}]})
            # Extract the final message content from the result
            output = ""
            if "messages" in result and len(result["messages"]) > 0:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    output = last_message.content
                elif isinstance(last_message, dict) and "content" in last_message:
                    output = last_message["content"]

            return {"status": "success", "agent_analysis": output, "processed": True}
        except Exception as e:
            return {"status": "error", "error": str(e), "processed": False}


def get_csv_analysis_agent() -> CSVAnalysisAgent:
    """Get or create CSV analysis agent instance."""
    if not hasattr(get_csv_analysis_agent, "_instance"):
        get_csv_analysis_agent._instance = CSVAnalysisAgent()
    return get_csv_analysis_agent._instance


def get_curation_agent() -> DataCurationAgent:
    """Get or create data curation agent instance."""
    if not hasattr(get_curation_agent, "_instance"):
        get_curation_agent._instance = DataCurationAgent()
    return get_curation_agent._instance


def get_monitoring_agent() -> PipelineMonitoringAgent:
    """Get or create pipeline monitoring agent instance."""
    if not hasattr(get_monitoring_agent, "_instance"):
        get_monitoring_agent._instance = PipelineMonitoringAgent()
    return get_monitoring_agent._instance
