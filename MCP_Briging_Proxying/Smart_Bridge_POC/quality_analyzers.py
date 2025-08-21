"""
Quality analysis tools integration
"""

import asyncio
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx
from quality_orchestrator import AnalysisResult, AnalysisStatus


class QualityAnalyzer:
    """Handles various quality analysis tools"""
    
    def __init__(self, workspace_path: str, config: Dict[str, Any]):
        self.workspace_path = Path(workspace_path)
        self.config = config
        self.serena_client = httpx.AsyncClient(timeout=30.0)
    
    async def run_serena_semantic_analysis(self, target_files: Optional[List[str]] = None) -> AnalysisResult:
        """Run Serena semantic analysis"""
        start_time = datetime.now()
        
        try:
            # Connect to local Serena MCP server
            serena_port = self.config.get("ports", {}).get("serena", 24282)
            
            # Request semantic analysis
            response = await self.serena_client.post(
                f"http://localhost:{serena_port}/analyze",
                json={
                    "files": target_files or [],
                    "analysis_type": "semantic",
                    "workspace": str(self.workspace_path)
                }
            )
            
            if response.status_code == 200:
                result_data = response.json()
                return AnalysisResult(
                    tool="serena",
                    status=AnalysisStatus.COMPLETED,
                    duration=(datetime.now() - start_time).total_seconds(),
                    output=result_data,
                    errors=[],
                    warnings=result_data.get("warnings", []),
                    started_at=start_time,
                    completed_at=datetime.now()
                )
            else:
                raise Exception(f"Serena analysis failed: {response.status_code}")
                
        except Exception as e:
            return AnalysisResult(
                tool="serena",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_python_linting(self, tool: str, target_files: Optional[List[str]] = None) -> AnalysisResult:
        """Run Python linting tools"""
        start_time = datetime.now()
        
        try:
            if tool == "pylint":
                result = await self._run_pylint(target_files)
            elif tool == "flake8":
                result = await self._run_flake8(target_files)
            else:
                raise Exception(f"Unknown Python linting tool: {tool}")
            
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.COMPLETED,
                duration=(datetime.now() - start_time).total_seconds(),
                output=result,
                errors=result.get("errors", []),
                warnings=result.get("warnings", []),
                started_at=start_time,
                completed_at=datetime.now()
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_javascript_linting(self, tool: str, target_files: Optional[List[str]] = None) -> AnalysisResult:
        """Run JavaScript linting tools"""
        start_time = datetime.now()
        
        try:
            if tool == "eslint":
                result = await self._run_eslint(target_files)
            else:
                raise Exception(f"Unknown JavaScript linting tool: {tool}")
            
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.COMPLETED,
                duration=(datetime.now() - start_time).total_seconds(),
                output=result,
                errors=result.get("errors", []),
                warnings=result.get("warnings", []),
                started_at=start_time,
                completed_at=datetime.now()
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_security_scan(self, tool: str) -> AnalysisResult:
        """Run security scanning tools"""
        start_time = datetime.now()
        
        try:
            if tool == "bandit":
                result = await self._run_bandit()
            elif tool == "safety":
                result = await self._run_safety()
            else:
                raise Exception(f"Unknown security tool: {tool}")
            
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.COMPLETED,
                duration=(datetime.now() - start_time).total_seconds(),
                output=result,
                errors=result.get("errors", []),
                warnings=result.get("warnings", []),
                started_at=start_time,
                completed_at=datetime.now()
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=tool,
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_lighthouse_audit(self) -> AnalysisResult:
        """Run Lighthouse performance audit"""
        start_time = datetime.now()
        
        try:
            # Look for common dev server ports
            possible_urls = [
                "http://localhost:3000",
                "http://localhost:8080", 
                "http://localhost:5000",
                "http://localhost:4200"
            ]
            
            target_url = None
            for url in possible_urls:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, timeout=5)
                        if response.status_code == 200:
                            target_url = url
                            break
                except:
                    continue
            
            if not target_url:
                raise Exception("No running web server found for Lighthouse audit")
            
            # Run Lighthouse
            cmd = [
                "lighthouse",
                target_url,
                "--output=json",
                "--output-path=/tmp/lighthouse-report.json",
                "--chrome-flags=--headless"
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                with open("/tmp/lighthouse-report.json") as f:
                    lighthouse_data = json.load(f)
                
                return AnalysisResult(
                    tool="lighthouse",
                    status=AnalysisStatus.COMPLETED,
                    duration=(datetime.now() - start_time).total_seconds(),
                    output=lighthouse_data,
                    errors=[],
                    warnings=[],
                    started_at=start_time,
                    completed_at=datetime.now()
                )
            else:
                raise Exception(f"Lighthouse failed: {stderr.decode()}")
                
        except Exception as e:
            return AnalysisResult(
                tool="lighthouse",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_clinic_analysis(self) -> AnalysisResult:
        """Run clinic.js performance analysis"""
        start_time = datetime.now()
        
        try:
            # Check for package.json and start script
            package_json = self.workspace_path / "package.json"
            if not package_json.exists():
                raise Exception("No package.json found for Node.js analysis")
            
            # Run clinic doctor
            cmd = ["clinic", "doctor", "--", "npm", "start"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )
            
            stdout, stderr = await proc.communicate()
            
            # For this POC, return basic result
            # In production, would parse clinic output
            return AnalysisResult(
                tool="clinic",
                status=AnalysisStatus.COMPLETED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={"stdout": stdout.decode(), "stderr": stderr.decode()},
                errors=[],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
            
        except Exception as e:
            return AnalysisResult(
                tool="clinic",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def _run_pylint(self, target_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run pylint analysis"""
        files_to_check = target_files or ["*.py"]
        
        cmd = ["pylint", "--output-format=json"] + files_to_check
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            pylint_output = json.loads(stdout.decode())
            return {
                "issues": pylint_output,
                "errors": [issue for issue in pylint_output if issue["type"] == "error"],
                "warnings": [issue for issue in pylint_output if issue["type"] == "warning"]
            }
        except json.JSONDecodeError:
            return {
                "raw_output": stdout.decode(),
                "errors": stderr.decode().split('\n') if stderr else [],
                "warnings": []
            }
    
    async def _run_flake8(self, target_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run flake8 analysis"""
        files_to_check = target_files or ["."]
        
        cmd = ["flake8", "--format=json"] + files_to_check
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        # Parse flake8 output (format: file:line:col: code message)
        issues = []
        for line in stdout.decode().split('\n'):
            if line.strip():
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    issues.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "column": int(parts[2]),
                        "message": parts[3].strip()
                    })
        
        return {
            "issues": issues,
            "errors": [issue for issue in issues if issue["message"].startswith("E")],
            "warnings": [issue for issue in issues if issue["message"].startswith("W")]
        }
    
    async def _run_eslint(self, target_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run ESLint analysis"""
        files_to_check = target_files or ["."]
        
        cmd = ["eslint", "--format=json"] + files_to_check
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            eslint_output = json.loads(stdout.decode())
            all_messages = []
            for file_result in eslint_output:
                all_messages.extend(file_result.get("messages", []))
            
            return {
                "files": eslint_output,
                "errors": [msg for msg in all_messages if msg["severity"] == 2],
                "warnings": [msg for msg in all_messages if msg["severity"] == 1]
            }
        except json.JSONDecodeError:
            return {
                "raw_output": stdout.decode(),
                "errors": stderr.decode().split('\n') if stderr else [],
                "warnings": []
            }
    
    async def _run_bandit(self) -> Dict[str, Any]:
        """Run Bandit security analysis"""
        cmd = ["bandit", "-r", ".", "-f", "json"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            bandit_output = json.loads(stdout.decode())
            return {
                "results": bandit_output.get("results", []),
                "errors": [result for result in bandit_output.get("results", []) 
                          if result.get("issue_severity") == "HIGH"],
                "warnings": [result for result in bandit_output.get("results", []) 
                           if result.get("issue_severity") in ["MEDIUM", "LOW"]]
            }
        except json.JSONDecodeError:
            return {
                "raw_output": stdout.decode(),
                "errors": [],
                "warnings": []
            }
    
    async def _run_safety(self) -> Dict[str, Any]:
        """Run Safety dependency vulnerability check"""
        cmd = ["safety", "check", "--json"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            safety_output = json.loads(stdout.decode())
            return {
                "vulnerabilities": safety_output,
                "errors": [vuln for vuln in safety_output if vuln.get("severity") == "high"],
                "warnings": [vuln for vuln in safety_output if vuln.get("severity") in ["medium", "low"]]
            }
        except json.JSONDecodeError:
            return {
                "raw_output": stdout.decode(),
                "errors": [],
                "warnings": []
            }