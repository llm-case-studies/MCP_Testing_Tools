"""
Test suite management API endpoints
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from ..models import TestSuite
from ..storage import test_suites, test_results
# Note: We'll import call_server_tool dynamically to avoid circular imports

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test-suites", tags=["test-suites"])


@router.post("")
async def create_test_suite(suite: TestSuite):
    """Create a new test suite"""
    test_suites[suite.name] = suite.dict()
    return {"message": f"Test suite {suite.name} created"}


@router.get("")
async def list_test_suites():
    """List all test suites"""
    return {"test_suites": list(test_suites.values())}


@router.post("/{suite_name}/run")
async def run_test_suite(suite_name: str):
    """Run a test suite"""
    if suite_name not in test_suites:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    suite = test_suites[suite_name]
    results = []
    
    for test in suite["tests"]:
        try:
            # Import call_server_tool dynamically to avoid circular imports
            from .tools import call_server_tool
            result = await call_server_tool(
                test["server_name"],
                test["tool_name"],
                test["parameters"]
            )
            results.append({
                "test": test,
                "result": result,
                "success": "error" not in result
            })
        except Exception as e:
            results.append({
                "test": test,
                "result": {"error": str(e)},
                "success": False
            })
    
    suite_result = {
        "suite_name": suite_name,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"])
    }
    
    return suite_result


