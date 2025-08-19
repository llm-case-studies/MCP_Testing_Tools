"""
Test results API endpoints
"""

import logging
from fastapi import APIRouter
from ..storage import test_results

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test-results", tags=["results"])


@router.get("")
async def get_test_results():
    """Get historical test results"""
    return {"results": test_results}


@router.delete("")
async def clear_test_results():
    """Clear all test results"""
    test_results.clear()
    return {"message": "Test results cleared"}