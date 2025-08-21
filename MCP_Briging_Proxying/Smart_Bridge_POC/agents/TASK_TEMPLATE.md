# Agent Task Template

## Bridge Implementer Task Specification

### **Case**: [Brief description like "SSE MCP to OpenAPI Bridge"]

### **Input Specification**:
- **Type**: [stdio/SSE/HTTP/WebSocket]  
- **Location**: [URL/command/file path]
- **Protocol**: [Detailed protocol specification]
- **Authentication**: [Auth requirements if any]

### **Output Specification**:
- **Type**: [SSE/OpenAPI/HTML/WebSocket]
- **Endpoint**: [URL pattern like /api/v1/tools]
- **Format**: [Response format specification]
- **Features**: [Required features like streaming, auth]

### **Requirements**:
- [ ] Session isolation for multiple clients
- [ ] Comprehensive structured logging
- [ ] Error handling with proper HTTP status codes
- [ ] Health checks and monitoring endpoints
- [ ] Timeout and retry logic
- [ ] Integration test compatibility
- [ ] Performance monitoring hooks

### **Logging Requirements**:
```python
# Required log format
logger.info("bridge_operation", extra={
    "operation": "tool_execution",
    "session_id": session_id,
    "tool_name": tool_name,
    "duration_ms": duration,
    "status": "success|error",
    "error_details": error_info
})
```

### **Directory Structure**:
```
agents/bridge-implementer/{case-name}/
├── bridge.py              # Main bridge implementation
├── config.py              # Configuration management
├── logs/                  # Log files directory
├── tests/                 # Unit tests
├── README.md              # Implementation documentation
└── requirements.txt       # Dependencies
```

### **Success Criteria**:
- [ ] Bridge works end-to-end with provided test input
- [ ] All logging requirements implemented
- [ ] Error scenarios handled gracefully
- [ ] Integration tests pass
- [ ] Documentation complete
- [ ] Code follows project standards

### **Deliverables**:
1. Working bridge implementation in specified directory
2. Comprehensive test suite
3. Configuration documentation
4. Performance characteristics report
5. Integration guide for main bridge

---

## Test Writer Task Specification

### **Target**: [Path to implementation to test]

### **Test Requirements**:
- [ ] Unit tests for core components (>90% coverage)
- [ ] Integration tests with mock servers
- [ ] Performance tests with load scenarios
- [ ] Error scenario testing
- [ ] Security testing (if applicable)
- [ ] Regression test suite

### **Test Types Needed**:
```python
# Unit Tests
test_session_management()
test_error_handling()
test_configuration()

# Integration Tests  
test_end_to_end_flow()
test_multiple_clients()
test_server_failures()

# Performance Tests
test_concurrent_clients()
test_large_payloads()
test_sustained_load()
```

### **Mock Requirements**:
- Mock input servers (stdio/SSE/HTTP)
- Mock client connections
- Configurable failure scenarios
- Performance simulation tools

### **Success Criteria**:
- [ ] All tests pass consistently
- [ ] Coverage reports meet standards
- [ ] Performance benchmarks established
- [ ] CI/CD integration ready
- [ ] Test documentation complete

---

## Research Task Specification (External AI)

### **Research Goal**: [Clear objective like "Find SSE MCP Servers"]

### **Scope**:
- **Domain**: [MCP servers/APIs/patterns]
- **Complexity**: [Simple/Medium/Complex]
- **Languages**: [Python/Node.js/Go/etc]
- **License**: [Open source/Commercial/Any]

### **Deliverables Required**:
1. **Curated List**: Top 5-10 candidates with ratings
2. **Setup Guides**: How to install and configure each
3. **Complexity Assessment**: Implementation difficulty (1-10)
4. **Documentation Quality**: How well documented (1-10) 
5. **Integration Notes**: Special considerations for bridging

### **Output Format**:
```markdown
# Research Results: [Goal]

## Top Candidates

### 1. [Name] - [Rating]/10
- **Repository**: [URL]
- **Language**: [Lang]
- **Complexity**: [1-10]
- **Setup**: [Brief steps]
- **Bridge Notes**: [Integration considerations]

## Implementation Recommendations
- **Best for Testing**: [Candidate with rationale]
- **Best for Production**: [Candidate with rationale]  
- **Avoid**: [Problematic options with reasons]
```

### **Success Criteria**:
- [ ] Actionable recommendations provided
- [ ] Setup instructions tested (where possible)
- [ ] Complexity estimates realistic
- [ ] Integration considerations identified
- [ ] Timeline estimates included

---

**Usage**: Copy this template and fill in specific requirements for each agent task.