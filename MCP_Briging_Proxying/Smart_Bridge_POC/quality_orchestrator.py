#!/usr/bin/env python3
"""
DevOps Paradise - Quality Orchestrator
Coordinates comprehensive testing and quality analysis pipeline with Serena integration
"""

import asyncio
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel

# Import our quality analysis modules
from quality_analyzers import QualityAnalyzer
from test_runners import TestRunner
from report_generator import ReportGenerator
from bridge_integration import BridgeIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/quality_orchestrator.log')
    ]
)
logger = logging.getLogger(__name__)

class QualityProfile(Enum):
    """Quality analysis profiles"""
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"

class AnalysisStatus(Enum):
    """Analysis execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AnalysisResult:
    """Individual analysis result"""
    tool: str
    status: AnalysisStatus
    duration: float
    output: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    started_at: datetime
    completed_at: Optional[datetime] = None

@dataclass
class QualityReport:
    """Comprehensive quality report"""
    client_id: str
    workspace_path: str
    profile: QualityProfile
    started_at: datetime
    completed_at: Optional[datetime]
    status: AnalysisStatus
    overall_score: float
    results: List[AnalysisResult]
    summary: Dict[str, Any]
    recommendations: List[str]

class QualityRequest(BaseModel):
    """API request model for quality analysis"""
    analysis_type: str = "comprehensive"
    target_files: Optional[List[str]] = None
    profile: str = "comprehensive"
    options: Dict[str, Any] = {}

class QualityOrchestrator:
    """Main orchestrator for quality analysis pipeline"""
    
    def __init__(self, client_id: str, workspace_path: str, config_path: str):
        self.client_id = client_id
        self.workspace_path = Path(workspace_path)
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.quality_analyzer = QualityAnalyzer(workspace_path, self.config)
        self.test_runner = TestRunner(workspace_path, self.config)
        self.report_generator = ReportGenerator(client_id, self.config)
        self.bridge_integration = BridgeIntegration(client_id)
        
        # Analysis state
        self.current_analysis: Optional[QualityReport] = None
        self.analysis_history: List[QualityReport] = []
        
        # FastAPI app for orchestrator API
        self.app = FastAPI(
            title="DevOps Paradise Quality Orchestrator",
            description="Comprehensive quality analysis and testing orchestration",
            version="1.0.0"
        )
        self._setup_routes()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            "quality_profile": "comprehensive",
            "analysis": {
                "semantic_analysis": True,
                "code_quality": True,
                "security_scanning": True,
                "performance_testing": True,
                "test_coverage": True
            },
            "tools": {
                "python": {
                    "linting": ["pylint", "flake8"],
                    "formatting": ["black", "isort"],
                    "testing": ["pytest"],
                    "type_checking": ["mypy"],
                    "security": ["bandit", "safety"]
                },
                "javascript": {
                    "linting": ["eslint"],
                    "formatting": ["prettier"],
                    "testing": ["jest", "playwright"],
                    "performance": ["lighthouse", "clinic"]
                }
            }
        }
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "client_id": self.client_id,
                "workspace": str(self.workspace_path),
                "current_analysis": self.current_analysis.status.value if self.current_analysis else None,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.post("/analyze")
        async def run_analysis(request: QualityRequest, background_tasks: BackgroundTasks):
            """Start quality analysis"""
            if self.current_analysis and self.current_analysis.status == AnalysisStatus.RUNNING:
                raise HTTPException(status_code=409, detail="Analysis already running")
            
            # Start analysis in background
            background_tasks.add_task(
                self._run_comprehensive_analysis,
                QualityProfile(request.profile),
                request.target_files,
                request.options
            )
            
            return {
                "message": "Analysis started",
                "analysis_type": request.analysis_type,
                "profile": request.profile,
                "estimated_duration": self._estimate_duration(request.profile)
            }
        
        @self.app.get("/status")
        async def get_status():
            """Get current analysis status"""
            if not self.current_analysis:
                return {"status": "idle", "message": "No analysis running"}
            
            return {
                "status": self.current_analysis.status.value,
                "progress": self._calculate_progress(),
                "current_step": self._get_current_step(),
                "started_at": self.current_analysis.started_at.isoformat(),
                "estimated_completion": self._estimate_completion()
            }
        
        @self.app.get("/results")
        async def get_results():
            """Get latest analysis results"""
            if not self.current_analysis:
                raise HTTPException(status_code=404, detail="No analysis results available")
            
            return {
                "report": asdict(self.current_analysis),
                "summary_url": f"/reports/{self.client_id}/latest",
                "dashboard_url": f"http://localhost:8000/quality/{self.client_id}"
            }
        
        @self.app.get("/history")
        async def get_history():
            """Get analysis history"""
            return {
                "client_id": self.client_id,
                "total_analyses": len(self.analysis_history),
                "history": [
                    {
                        "started_at": report.started_at.isoformat(),
                        "status": report.status.value,
                        "profile": report.profile.value,
                        "score": report.overall_score,
                        "duration": (report.completed_at - report.started_at).total_seconds() 
                                  if report.completed_at else None
                    }
                    for report in self.analysis_history[-10:]  # Last 10 analyses
                ]
            }
        
        @self.app.post("/cancel")
        async def cancel_analysis():
            """Cancel current analysis"""
            if not self.current_analysis or self.current_analysis.status != AnalysisStatus.RUNNING:
                raise HTTPException(status_code=400, detail="No analysis running to cancel")
            
            self.current_analysis.status = AnalysisStatus.CANCELLED
            return {"message": "Analysis cancelled"}
    
    async def _run_comprehensive_analysis(
        self, 
        profile: QualityProfile,
        target_files: Optional[List[str]] = None,
        options: Dict[str, Any] = {}
    ):
        """Run comprehensive quality analysis"""
        logger.info(f"Starting comprehensive analysis for client {self.client_id}")
        
        # Initialize analysis report
        self.current_analysis = QualityReport(
            client_id=self.client_id,
            workspace_path=str(self.workspace_path),
            profile=profile,
            started_at=datetime.now(),
            completed_at=None,
            status=AnalysisStatus.RUNNING,
            overall_score=0.0,
            results=[],
            summary={},
            recommendations=[]
        )
        
        try:
            # Step 1: Semantic Analysis with Serena
            if self.config["analysis"]["semantic_analysis"]:
                logger.info("Running Serena semantic analysis...")
                serena_result = await self._run_serena_analysis(target_files)
                self.current_analysis.results.append(serena_result)
            
            # Step 2: Code Quality Analysis
            if self.config["analysis"]["code_quality"]:
                logger.info("Running code quality analysis...")
                quality_results = await self._run_quality_analysis(target_files)
                self.current_analysis.results.extend(quality_results)
            
            # Step 3: Security Scanning
            if self.config["analysis"]["security_scanning"]:
                logger.info("Running security analysis...")
                security_results = await self._run_security_analysis()
                self.current_analysis.results.extend(security_results)
            
            # Step 4: Test Execution
            test_results = await self._run_test_analysis(profile)
            self.current_analysis.results.extend(test_results)
            
            # Step 5: Performance Analysis
            if self.config["analysis"]["performance_testing"]:
                logger.info("Running performance analysis...")
                perf_results = await self._run_performance_analysis()
                self.current_analysis.results.extend(perf_results)
            
            # Step 6: Generate comprehensive report
            logger.info("Generating comprehensive report...")
            await self._generate_final_report()
            
            # Mark as completed
            self.current_analysis.status = AnalysisStatus.COMPLETED
            self.current_analysis.completed_at = datetime.now()
            
            # Add to history
            self.analysis_history.append(self.current_analysis)
            
            # Notify bridge of completion
            await self.bridge_integration.notify_analysis_complete(self.current_analysis)
            
            logger.info(f"Analysis completed successfully. Score: {self.current_analysis.overall_score}")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self.current_analysis.status = AnalysisStatus.FAILED
            self.current_analysis.completed_at = datetime.now()
            
            # Add error to results
            error_result = AnalysisResult(
                tool="orchestrator",
                status=AnalysisStatus.FAILED,
                duration=0,
                output={},
                errors=[str(e)],
                warnings=[],
                started_at=datetime.now()
            )
            self.current_analysis.results.append(error_result)
    
    async def _run_serena_analysis(self, target_files: Optional[List[str]]) -> AnalysisResult:
        """Run Serena semantic analysis"""
        start_time = datetime.now()
        
        try:
            # Connect to Serena MCP server
            result = await self.quality_analyzer.run_serena_semantic_analysis(target_files)
            
            return AnalysisResult(
                tool="serena",
                status=AnalysisStatus.COMPLETED,
                duration=(datetime.now() - start_time).total_seconds(),
                output=result,
                errors=[],
                warnings=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
            
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
    
    async def _run_quality_analysis(self, target_files: Optional[List[str]]) -> List[AnalysisResult]:
        """Run code quality analysis"""
        results = []
        
        # Python quality tools
        if self._has_python_files(target_files):
            for tool in self.config["tools"]["python"]["linting"]:
                result = await self.quality_analyzer.run_python_linting(tool, target_files)
                results.append(result)
        
        # JavaScript quality tools
        if self._has_javascript_files(target_files):
            for tool in self.config["tools"]["javascript"]["linting"]:
                result = await self.quality_analyzer.run_javascript_linting(tool, target_files)
                results.append(result)
        
        return results
    
    async def _run_security_analysis(self) -> List[AnalysisResult]:
        """Run security analysis"""
        results = []
        
        # Python security tools
        if self._has_python_files():
            for tool in self.config["tools"]["python"]["security"]:
                result = await self.quality_analyzer.run_security_scan(tool)
                results.append(result)
        
        return results
    
    async def _run_test_analysis(self, profile: QualityProfile) -> List[AnalysisResult]:
        """Run test suite analysis"""
        results = []
        
        # Unit tests
        if profile in [QualityProfile.STANDARD, QualityProfile.COMPREHENSIVE]:
            unit_result = await self.test_runner.run_unit_tests()
            results.append(unit_result)
        
        # Integration tests
        if profile == QualityProfile.COMPREHENSIVE:
            integration_result = await self.test_runner.run_integration_tests()
            results.append(integration_result)
            
            # E2E tests
            e2e_result = await self.test_runner.run_e2e_tests()
            results.append(e2e_result)
            
            # API tests
            api_result = await self.test_runner.run_api_tests()
            results.append(api_result)
        
        return results
    
    async def _run_performance_analysis(self) -> List[AnalysisResult]:
        """Run performance analysis"""
        results = []
        
        # Lighthouse audit (if web app detected)
        if self._has_web_app():
            lighthouse_result = await self.quality_analyzer.run_lighthouse_audit()
            results.append(lighthouse_result)
        
        # Node.js performance (if Node.js app detected)
        if self._has_nodejs_app():
            clinic_result = await self.quality_analyzer.run_clinic_analysis()
            results.append(clinic_result)
        
        return results
    
    async def _generate_final_report(self):
        """Generate final comprehensive report"""
        # Calculate overall score
        self.current_analysis.overall_score = self._calculate_overall_score()
        
        # Generate summary
        self.current_analysis.summary = self._generate_summary()
        
        # Generate recommendations
        self.current_analysis.recommendations = self._generate_recommendations()
        
        # Generate report files
        await self.report_generator.generate_comprehensive_report(self.current_analysis)
    
    def _calculate_overall_score(self) -> float:
        """Calculate overall quality score (0-100)"""
        if not self.current_analysis.results:
            return 0.0
        
        total_score = 0.0
        weight_sum = 0.0
        
        # Weight different analysis types
        weights = {
            "serena": 0.3,      # Semantic analysis - high weight
            "pylint": 0.15,     # Code quality
            "eslint": 0.15,     # Code quality
            "pytest": 0.15,     # Testing
            "bandit": 0.10,     # Security
            "lighthouse": 0.10, # Performance
            "default": 0.05     # Other tools
        }
        
        for result in self.current_analysis.results:
            if result.status == AnalysisStatus.COMPLETED:
                tool_score = self._extract_score_from_result(result)
                weight = weights.get(result.tool, weights["default"])
                total_score += tool_score * weight
                weight_sum += weight
        
        return (total_score / weight_sum) if weight_sum > 0 else 0.0
    
    def _extract_score_from_result(self, result: AnalysisResult) -> float:
        """Extract score from analysis result"""
        # This would contain tool-specific score extraction logic
        # For now, return a basic score based on errors/warnings
        if result.errors:
            return max(0.0, 60.0 - len(result.errors) * 10)
        elif result.warnings:
            return max(70.0, 85.0 - len(result.warnings) * 5)
        else:
            return 95.0
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate analysis summary"""
        return {
            "total_tools_run": len(self.current_analysis.results),
            "successful_tools": len([r for r in self.current_analysis.results if r.status == AnalysisStatus.COMPLETED]),
            "failed_tools": len([r for r in self.current_analysis.results if r.status == AnalysisStatus.FAILED]),
            "total_errors": sum(len(r.errors) for r in self.current_analysis.results),
            "total_warnings": sum(len(r.warnings) for r in self.current_analysis.results),
            "execution_time": (datetime.now() - self.current_analysis.started_at).total_seconds()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Analyze results and generate recommendations
        for result in self.current_analysis.results:
            if result.errors:
                recommendations.append(f"Fix {len(result.errors)} errors in {result.tool}")
            if result.warnings:
                recommendations.append(f"Address {len(result.warnings)} warnings in {result.tool}")
        
        # Add general recommendations based on score
        if self.current_analysis.overall_score < 70:
            recommendations.append("Consider implementing automated testing")
            recommendations.append("Review code quality standards")
        
        return recommendations
    
    def _has_python_files(self, target_files: Optional[List[str]] = None) -> bool:
        """Check if workspace has Python files"""
        if target_files:
            return any(f.endswith('.py') for f in target_files)
        return any(self.workspace_path.rglob('*.py'))
    
    def _has_javascript_files(self, target_files: Optional[List[str]] = None) -> bool:
        """Check if workspace has JavaScript files"""
        if target_files:
            return any(f.endswith(('.js', '.ts', '.jsx', '.tsx')) for f in target_files)
        return any(self.workspace_path.rglob('*.js')) or any(self.workspace_path.rglob('*.ts'))
    
    def _has_web_app(self) -> bool:
        """Check if workspace has a web application"""
        return (self.workspace_path / 'package.json').exists() or \
               (self.workspace_path / 'index.html').exists()
    
    def _has_nodejs_app(self) -> bool:
        """Check if workspace has a Node.js application"""
        return (self.workspace_path / 'package.json').exists()
    
    def _calculate_progress(self) -> float:
        """Calculate analysis progress percentage"""
        if not self.current_analysis:
            return 0.0
        
        total_steps = 6  # Number of analysis steps
        completed_steps = len([r for r in self.current_analysis.results 
                             if r.status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]])
        
        return min(100.0, (completed_steps / total_steps) * 100)
    
    def _get_current_step(self) -> str:
        """Get current analysis step"""
        if not self.current_analysis:
            return "idle"
        
        completed_count = len(self.current_analysis.results)
        steps = [
            "Semantic Analysis",
            "Code Quality",
            "Security Scanning", 
            "Test Execution",
            "Performance Analysis",
            "Report Generation"
        ]
        
        if completed_count < len(steps):
            return steps[completed_count]
        return "Completing..."
    
    def _estimate_duration(self, profile: str) -> int:
        """Estimate analysis duration in seconds"""
        durations = {
            "basic": 120,       # 2 minutes
            "standard": 300,    # 5 minutes
            "comprehensive": 600 # 10 minutes
        }
        return durations.get(profile, 300)
    
    def _estimate_completion(self) -> Optional[str]:
        """Estimate completion time"""
        if not self.current_analysis:
            return None
        
        progress = self._calculate_progress()
        if progress == 0:
            return None
        
        elapsed = (datetime.now() - self.current_analysis.started_at).total_seconds()
        estimated_total = elapsed / (progress / 100)
        remaining = estimated_total - elapsed
        
        completion_time = datetime.now().timestamp() + remaining
        return datetime.fromtimestamp(completion_time).isoformat()

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="DevOps Paradise Quality Orchestrator")
    parser.add_argument("--client-id", required=True, help="Client ID")
    parser.add_argument("--workspace", required=True, help="Workspace path")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--port", type=int, default=9000, help="API port")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Create orchestrator
    orchestrator = QualityOrchestrator(
        client_id=args.client_id,
        workspace_path=args.workspace,
        config_path=args.config
    )
    
    # Start API server
    logger.info(f"Starting Quality Orchestrator API on port {args.port}")
    config = uvicorn.Config(
        orchestrator.app,
        host="0.0.0.0",
        port=args.port,
        log_level=args.log_level.lower()
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())