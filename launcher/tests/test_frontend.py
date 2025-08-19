#!/usr/bin/env python3
"""
Tests for the refactored frontend serving
"""

import pytest
from fastapi.testclient import TestClient

from launcher.main import app

client = TestClient(app)

def test_serve_index_html():
    """Test that the root URL serves the index.html file"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>MCP Testing Suite V2 - Project Launcher</title>" in response.text

def test_serve_static_css():
    """Test that the CSS file is served correctly"""
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert "body {" in response.text

def test_serve_static_js():
    """Test that the JavaScript file is served correctly"""
    response = client.get("/static/script.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    assert "function switchToLearningMode()" in response.text
