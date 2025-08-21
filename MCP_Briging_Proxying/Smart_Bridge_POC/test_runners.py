"""
Test execution and orchestration
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from quality_orchestrator import AnalysisResult, AnalysisStatus


class TestRunner:
    """Handles various testing framework executions"""
    
    def __init__(self, workspace_path: str, config: Dict[str, Any]):
        self.workspace_path = Path(workspace_path)
        self.config = config
    
    async def run_unit_tests(self) -> AnalysisResult:
        """Run unit tests based on detected frameworks"""
        start_time = datetime.now()
        
        try:
            # Detect testing framework
            if self._has_pytest():
                result = await self._run_pytest()
            elif self._has_jest():
                result = await self._run_jest()
            else:
                raise Exception("No supported unit testing framework found")
            
            return AnalysisResult(
                tool="unit_tests",
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
                tool="unit_tests",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_integration_tests(self) -> AnalysisResult:
        """Run integration tests"""
        start_time = datetime.now()
        
        try:
            # Look for integration test patterns
            if self._has_pytest():
                result = await self._run_pytest(test_type="integration")
            elif self._has_jest():
                result = await self._run_jest(test_type="integration")
            else:
                result = {"message": "No integration tests found", "tests_run": 0}
            
            return AnalysisResult(
                tool="integration_tests",
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
                tool="integration_tests",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_e2e_tests(self) -> AnalysisResult:
        """Run end-to-end tests with Playwright"""
        start_time = datetime.now()
        
        try:
            if self._has_playwright():
                result = await self._run_playwright()
            else:
                result = {"message": "No Playwright tests found", "tests_run": 0}
            
            return AnalysisResult(
                tool="e2e_tests",
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
                tool="e2e_tests",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    async def run_api_tests(self) -> AnalysisResult:
        """Run API tests with Newman"""
        start_time = datetime.now()
        
        try:
            if self._has_postman_collections():
                result = await self._run_newman()
            else:
                result = {"message": "No Postman collections found", "tests_run": 0}
            
            return AnalysisResult(
                tool="api_tests",
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
                tool="api_tests",
                status=AnalysisStatus.FAILED,
                duration=(datetime.now() - start_time).total_seconds(),
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
    
    def _has_pytest(self) -> bool:
        """Check if pytest is available"""
        return (self.workspace_path / "pytest.ini").exists() or \
               any(self.workspace_path.rglob("test_*.py")) or \
               any(self.workspace_path.rglob("*_test.py"))
    
    def _has_jest(self) -> bool:
        """Check if Jest is available"""
        package_json = self.workspace_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    return "jest" in data.get("devDependencies", {}) or \
                           "jest" in data.get("dependencies", {}) or \
                           any("test" in script for script in data.get("scripts", {}).values())
            except:
                pass
        return any(self.workspace_path.rglob("*.test.js")) or \
               any(self.workspace_path.rglob("*.spec.js"))
    
    def _has_playwright(self) -> bool:
        """Check if Playwright tests exist"""
        return any(self.workspace_path.rglob("*.spec.ts")) or \
               any(self.workspace_path.rglob("e2e/**/*.ts")) or \
               (self.workspace_path / "playwright.config.ts").exists()
    
    def _has_postman_collections(self) -> bool:
        """Check if Postman collections exist"""
        return any(self.workspace_path.rglob("*.postman_collection.json"))
    
    async def _run_pytest(self, test_type: str = "unit") -> Dict[str, Any]:
        """Run pytest with coverage"""
        if test_type == "integration":
            # Look for integration test directories
            test_patterns = ["tests/integration", "integration_tests", "tests/*integration*"]
            cmd = ["pytest", "--json-report", "--json-report-file=/tmp/pytest-report.json", "-v"]
            for pattern in test_patterns:
                if any(self.workspace_path.glob(pattern)):
                    cmd.append(pattern)
                    break
            else:
                return {"message": "No integration tests found", "tests_run": 0}
        else:
            cmd = [
                "pytest",
                "--cov=.",
                "--cov-report=json:/tmp/coverage.json",
                "--json-report",
                "--json-report-file=/tmp/pytest-report.json",
                "-v"
            ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        # Parse pytest JSON report
        result = {
            "return_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }
        
        try:
            with open("/tmp/pytest-report.json") as f:
                pytest_data = json.load(f)
                result["test_results"] = pytest_data
                result["tests_run"] = pytest_data.get("summary", {}).get("total", 0)
                result["passed"] = pytest_data.get("summary", {}).get("passed", 0)
                result["failed"] = pytest_data.get("summary", {}).get("failed", 0)
                result["errors"] = [test for test in pytest_data.get("tests", []) 
                                 if test.get("outcome") == "failed"]
        except:
            pass
        
        # Parse coverage if available
        try:
            with open("/tmp/coverage.json") as f:
                coverage_data = json.load(f)
                result["coverage"] = coverage_data
        except:
            pass
        
        return result
    
    async def _run_jest(self, test_type: str = "unit") -> Dict[str, Any]:
        """Run Jest tests"""
        if test_type == "integration":
            cmd = ["npm", "test", "--", "--testPathPattern=integration", "--json"]
        else:
            cmd = ["npm", "test", "--", "--coverage", "--json"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        result = {
            "return_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }
        
        try:
            # Parse Jest output (last line is usually JSON)
            lines = stdout.decode().strip().split('\n')
            for line in reversed(lines):
                try:
                    jest_data = json.loads(line)
                    result["test_results"] = jest_data
                    result["tests_run"] = jest_data.get("numTotalTests", 0)
                    result["passed"] = jest_data.get("numPassedTests", 0)
                    result["failed"] = jest_data.get("numFailedTests", 0)
                    break
                except:
                    continue
        except:
            pass
        
        return result
    
    async def _run_playwright(self) -> Dict[str, Any]:
        """Run Playwright E2E tests"""
        cmd = ["npx", "playwright", "test", "--reporter=json"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path
        )
        
        stdout, stderr = await proc.communicate()
        
        result = {
            "return_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }
        
        try:
            playwright_data = json.loads(stdout.decode())
            result["test_results"] = playwright_data
            
            # Count test results
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            
            for suite in playwright_data.get("suites", []):
                for test in suite.get("tests", []):
                    total_tests += 1
                    for result_item in test.get("results", []):
                        if result_item.get("status") == "passed":
                            passed_tests += 1
                        elif result_item.get("status") == "failed":
                            failed_tests += 1
            
            result["tests_run"] = total_tests
            result["passed"] = passed_tests
            result["failed"] = failed_tests
            
        except:
            pass
        
        return result
    
    async def _run_newman(self) -> Dict[str, Any]:
        """Run Newman API tests"""
        # Find Postman collections
        collections = list(self.workspace_path.rglob("*.postman_collection.json"))
        
        if not collections:
            return {"message": "No Postman collections found", "tests_run": 0}
        
        results = []
        
        for collection in collections:
            cmd = ["newman", "run", str(collection), "--reporters", "json", "--reporter-json-export", "/tmp/newman-report.json"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )
            
            stdout, stderr = await proc.communicate()
            
            collection_result = {
                "collection": collection.name,
                "return_code": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode()
            }
            
            try:
                with open("/tmp/newman-report.json") as f:
                    newman_data = json.load(f)
                    collection_result["results"] = newman_data
                    
                    # Extract key metrics
                    run_stats = newman_data.get("run", {}).get("stats", {})
                    collection_result["tests_run"] = run_stats.get("tests", {}).get("total", 0)
                    collection_result["passed"] = run_stats.get("tests", {}).get("passed", 0)
                    collection_result["failed"] = run_stats.get("tests", {}).get("failed", 0)
                    
            except:
                pass
            
            results.append(collection_result)
        
        # Aggregate results
        total_tests = sum(r.get("tests_run", 0) for r in results)
        total_passed = sum(r.get("passed", 0) for r in results)
        total_failed = sum(r.get("failed", 0) for r in results)
        
        return {
            "collections": results,
            "tests_run": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "errors": [r for r in results if r.get("failed", 0) > 0]
        }