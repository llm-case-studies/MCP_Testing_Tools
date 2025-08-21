"""
Integration with DevOps Paradise Bridge
"""

import asyncio
import json
from typing import Dict, Any, Optional

import httpx

from quality_orchestrator import QualityReport


class BridgeIntegration:
    """Handles communication with the main DevOps Paradise Bridge"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.bridge_url = "http://localhost:8100"  # Main bridge URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def notify_analysis_start(self, analysis_type: str, profile: str):
        """Notify bridge that analysis has started"""
        try:
            await self.client.post(
                f"{self.bridge_url}/clients/{self.client_id}/analysis/start",
                json={
                    "analysis_type": analysis_type,
                    "profile": profile,
                    "timestamp": "now"
                }
            )
        except Exception as e:
            # Don't fail analysis if bridge communication fails
            print(f"Failed to notify bridge of analysis start: {e}")
    
    async def notify_analysis_complete(self, quality_report: QualityReport):
        """Notify bridge that analysis has completed"""
        try:
            report_summary = {
                "client_id": self.client_id,
                "status": quality_report.status.value,
                "overall_score": quality_report.overall_score,
                "started_at": quality_report.started_at.isoformat(),
                "completed_at": quality_report.completed_at.isoformat() if quality_report.completed_at else None,
                "profile": quality_report.profile.value,
                "summary": quality_report.summary,
                "recommendations_count": len(quality_report.recommendations),
                "tools_executed": len(quality_report.results),
                "errors_found": sum(len(r.errors) for r in quality_report.results),
                "warnings_found": sum(len(r.warnings) for r in quality_report.results)
            }
            
            await self.client.post(
                f"{self.bridge_url}/clients/{self.client_id}/analysis/complete",
                json=report_summary
            )
        except Exception as e:
            print(f"Failed to notify bridge of analysis completion: {e}")
    
    async def update_analysis_progress(self, progress: float, current_step: str):
        """Update analysis progress on bridge"""
        try:
            await self.client.patch(
                f"{self.bridge_url}/clients/{self.client_id}/analysis/progress",
                json={
                    "progress": progress,
                    "current_step": current_step,
                    "timestamp": "now"
                }
            )
        except Exception as e:
            print(f"Failed to update analysis progress: {e}")
    
    async def get_client_config(self) -> Optional[Dict[str, Any]]:
        """Get client configuration from bridge"""
        try:
            response = await self.client.get(
                f"{self.bridge_url}/clients/{self.client_id}/config"
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Failed to get client config: {e}")
        
        return None
    
    async def report_tool_result(self, tool_name: str, result: Dict[str, Any]):
        """Report individual tool results to bridge"""
        try:
            await self.client.post(
                f"{self.bridge_url}/clients/{self.client_id}/tools/{tool_name}/result",
                json=result
            )
        except Exception as e:
            print(f"Failed to report tool result for {tool_name}: {e}")
    
    async def health_check(self) -> bool:
        """Check if bridge is healthy"""
        try:
            response = await self.client.get(f"{self.bridge_url}/health")
            return response.status_code == 200
        except:
            return False