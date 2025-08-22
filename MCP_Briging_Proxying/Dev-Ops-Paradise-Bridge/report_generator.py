"""
Report generation and formatting
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from jinja2 import Template

from quality_orchestrator import QualityReport


class ReportGenerator:
    """Generates comprehensive quality reports in multiple formats"""
    
    def __init__(self, client_id: str, config: Dict[str, Any]):
        self.client_id = client_id
        self.config = config
        self.reports_dir = Path(f"/app/reports/{client_id}")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_comprehensive_report(self, quality_report: QualityReport):
        """Generate comprehensive report in multiple formats"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate JSON report
        await self._generate_json_report(quality_report, timestamp)
        
        # Generate HTML report
        await self._generate_html_report(quality_report, timestamp)
        
        # Generate markdown summary
        await self._generate_markdown_report(quality_report, timestamp)
        
        # Create symlink to latest
        await self._update_latest_links(timestamp)
    
    async def _generate_json_report(self, quality_report: QualityReport, timestamp: str):
        """Generate JSON report for programmatic access"""
        report_path = self.reports_dir / f"quality_report_{timestamp}.json"
        
        # Convert report to dict and make it JSON serializable
        report_dict = {
            "client_id": quality_report.client_id,
            "workspace_path": quality_report.workspace_path,
            "profile": quality_report.profile.value,
            "started_at": quality_report.started_at.isoformat(),
            "completed_at": quality_report.completed_at.isoformat() if quality_report.completed_at else None,
            "status": quality_report.status.value,
            "overall_score": quality_report.overall_score,
            "summary": quality_report.summary,
            "recommendations": quality_report.recommendations,
            "results": []
        }
        
        # Add results
        for result in quality_report.results:
            result_dict = {
                "tool": result.tool,
                "status": result.status.value,
                "duration": result.duration,
                "output": result.output,
                "errors": result.errors,
                "warnings": result.warnings,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None
            }
            report_dict["results"].append(result_dict)
        
        with open(report_path, 'w') as f:
            json.dump(report_dict, f, indent=2)
    
    async def _generate_html_report(self, quality_report: QualityReport, timestamp: str):
        """Generate HTML report for human consumption"""
        report_path = self.reports_dir / f"quality_report_{timestamp}.html"
        
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevOps Paradise Quality Report - {{ client_id }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { border-bottom: 2px solid #007acc; padding-bottom: 20px; margin-bottom: 30px; }
        .header h1 { color: #007acc; margin: 0; font-size: 2.5em; }
        .header .subtitle { color: #666; font-size: 1.2em; margin-top: 5px; }
        .score-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
        .score-number { font-size: 4em; font-weight: bold; margin: 0; }
        .score-label { font-size: 1.2em; opacity: 0.9; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007acc; }
        .metric-label { color: #666; margin-top: 5px; }
        .section { margin-bottom: 30px; }
        .section h2 { color: #333; border-left: 4px solid #007acc; padding-left: 15px; }
        .tool-result { background: #f8f9fa; margin: 10px 0; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745; }
        .tool-result.failed { border-left-color: #dc3545; }
        .tool-name { font-weight: bold; color: #007acc; }
        .status { padding: 3px 8px; border-radius: 3px; font-size: 0.9em; }
        .status.completed { background: #d4edda; color: #155724; }
        .status.failed { background: #f8d7da; color: #721c24; }
        .errors, .warnings { margin-top: 10px; }
        .error { color: #dc3545; margin: 5px 0; }
        .warning { color: #856404; margin: 5px 0; }
        .recommendations { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 20px; }
        .recommendation { margin: 10px 0; padding: 10px; background: white; border-radius: 3px; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌉 DevOps Paradise Quality Report</h1>
            <div class="subtitle">Client: {{ client_id }} | {{ completed_at }}</div>
        </div>
        
        <div class="score-card">
            <div class="score-number">{{ "%.0f"|format(overall_score) }}</div>
            <div class="score-label">Overall Quality Score</div>
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{{ summary.total_tools_run }}</div>
                <div class="metric-label">Tools Executed</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ summary.successful_tools }}</div>
                <div class="metric-label">Successful</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ summary.total_errors }}</div>
                <div class="metric-label">Errors Found</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ "%.1f"|format(summary.execution_time) }}s</div>
                <div class="metric-label">Execution Time</div>
            </div>
        </div>
        
        <div class="section">
            <h2>Analysis Results</h2>
            {% for result in results %}
            <div class="tool-result {% if result.status == 'failed' %}failed{% endif %}">
                <div class="tool-name">{{ result.tool|title }}</div>
                <span class="status {{ result.status }}">{{ result.status|title }}</span>
                <div>Duration: {{ "%.2f"|format(result.duration) }}s</div>
                
                {% if result.errors %}
                <div class="errors">
                    <strong>Errors:</strong>
                    {% for error in result.errors %}
                    <div class="error">❌ {{ error }}</div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if result.warnings %}
                <div class="warnings">
                    <strong>Warnings:</strong>
                    {% for warning in result.warnings %}
                    <div class="warning">⚠️ {{ warning }}</div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        {% if recommendations %}
        <div class="section">
            <h2>Recommendations</h2>
            <div class="recommendations">
                {% for rec in recommendations %}
                <div class="recommendation">💡 {{ rec }}</div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <p>Generated by DevOps Paradise Bridge | {{ timestamp }}</p>
            <p>Workspace: {{ workspace_path }}</p>
        </div>
    </div>
</body>
</html>
        """
        
        template = Template(html_template)
        html_content = template.render(
            client_id=quality_report.client_id,
            workspace_path=quality_report.workspace_path,
            overall_score=quality_report.overall_score,
            summary=quality_report.summary,
            results=quality_report.results,
            recommendations=quality_report.recommendations,
            completed_at=quality_report.completed_at.strftime("%Y-%m-%d %H:%M:%S") if quality_report.completed_at else "In Progress",
            timestamp=timestamp
        )
        
        with open(report_path, 'w') as f:
            f.write(html_content)
    
    async def _generate_markdown_report(self, quality_report: QualityReport, timestamp: str):
        """Generate Markdown report for documentation"""
        report_path = self.reports_dir / f"quality_report_{timestamp}.md"
        
        md_content = f"""# DevOps Paradise Quality Report

**Client:** {quality_report.client_id}  
**Workspace:** {quality_report.workspace_path}  
**Profile:** {quality_report.profile.value}  
**Generated:** {quality_report.completed_at.strftime("%Y-%m-%d %H:%M:%S") if quality_report.completed_at else "In Progress"}

## Overall Score: {quality_report.overall_score:.0f}/100

## Summary

| Metric | Value |
|--------|-------|
| Tools Executed | {quality_report.summary.get('total_tools_run', 0)} |
| Successful | {quality_report.summary.get('successful_tools', 0)} |
| Failed | {quality_report.summary.get('failed_tools', 0)} |
| Total Errors | {quality_report.summary.get('total_errors', 0)} |
| Total Warnings | {quality_report.summary.get('total_warnings', 0)} |
| Execution Time | {quality_report.summary.get('execution_time', 0):.1f}s |

## Analysis Results

"""
        
        for result in quality_report.results:
            status_emoji = "✅" if result.status.value == "completed" else "❌"
            md_content += f"""
### {status_emoji} {result.tool.title()}

- **Status:** {result.status.value}
- **Duration:** {result.duration:.2f}s
"""
            
            if result.errors:
                md_content += "\n**Errors:**\n"
                for error in result.errors:
                    md_content += f"- ❌ {error}\n"
            
            if result.warnings:
                md_content += "\n**Warnings:**\n"
                for warning in result.warnings:
                    md_content += f"- ⚠️ {warning}\n"
            
            md_content += "\n"
        
        if quality_report.recommendations:
            md_content += "\n## Recommendations\n\n"
            for rec in quality_report.recommendations:
                md_content += f"- 💡 {rec}\n"
        
        md_content += f"""
---

*Generated by DevOps Paradise Bridge at {timestamp}*
"""
        
        with open(report_path, 'w') as f:
            f.write(md_content)
    
    async def _update_latest_links(self, timestamp: str):
        """Create symlinks to latest reports"""
        latest_json = self.reports_dir / "latest.json"
        latest_html = self.reports_dir / "latest.html"
        latest_md = self.reports_dir / "latest.md"
        
        # Remove existing symlinks
        for link in [latest_json, latest_html, latest_md]:
            if link.exists():
                link.unlink()
        
        # Create new symlinks
        latest_json.symlink_to(f"quality_report_{timestamp}.json")
        latest_html.symlink_to(f"quality_report_{timestamp}.html")
        latest_md.symlink_to(f"quality_report_{timestamp}.md")