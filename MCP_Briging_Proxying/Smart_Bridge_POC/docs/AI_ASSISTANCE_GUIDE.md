# AI Assistance Guide - Who Does What

## 🤖 AI Role Assignments for Generic Bridge Development

### **Claude Code (This Session) - Architecture & Implementation**

#### **Perfect For:**
- ✅ Complex bridge implementation and async/streaming code
- ✅ Protocol handling and message correlation debugging  
- ✅ Architecture decisions and refactoring
- ✅ Integration testing and systematic debugging
- ✅ FastAPI, WebSocket, SSE implementations

#### **Current Tasks:**
- **Task 1.1**: Create minimal echo MCP server
- **Task 1.2**: Add byte-level stdio logging
- **Task 1.3**: Process state monitoring  
- **Task 2.2**: SSE-to-SSE bridge implementation
- **Task 3.2**: REST-to-MCP adapter pattern
- **Task 4.1**: OpenAPI interface exposure

#### **Communication Style:**
```
Alex: "Let's implement Task 1.1 - create the echo MCP server"
Claude Code: [Implements with detailed code and testing]
```

---

### **Claude Web - Research & Specifications**

#### **Perfect For:**
- 🔍 MCP protocol research and specification analysis
- 🔍 Finding existing MCP servers and implementations  
- 🔍 API design patterns and best practices research
- 🔍 Performance optimization techniques
- 🔍 Security and authentication patterns

#### **Current Tasks:**
- **Task 2.1**: Research existing SSE MCP server implementations
- **Task 3.1**: Research suitable test REST APIs
- **General**: MCP protocol deep dive and compliance research

#### **Communication Style:**
```
Alex: "Research existing SSE MCP servers for Task 2.1"
Claude Web: [Provides research summary with links and options]
```

---

### **Specialized AI Tools**

#### **Codeium/GitHub Copilot**
- **Role**: Code completion and routine implementation
- **Use For**: Boilerplate code, repetitive patterns, quick fixes
- **Integration**: VS Code, IDE plugins

#### **Postman AI**  
- **Role**: API testing and OpenAPI generation
- **Use For**: REST API testing, documentation generation
- **Integration**: Postman workspace automation

#### **Testing AI**
- **Role**: Test case generation and validation
- **Use For**: Unit tests, integration tests, edge cases
- **Integration**: pytest, jest test generation

---

### **Human Expert (Alex) - Strategy & Integration**

#### **Perfect For:**
- 🎯 Strategic decisions and priority setting
- 🎯 Real-world use case validation
- 🎯 Integration with existing systems
- 🎯 Performance requirements and acceptance criteria
- 🎯 User experience and developer workflow decisions

#### **Decision Points:**
- Which server types to prioritize
- Performance vs complexity tradeoffs  
- Integration patterns with existing infrastructure
- When to ship vs when to optimize

---

## 📋 Task Assignment Quick Reference

### **Immediate Sprint (This Week)**

| Task | AI Assignment | Estimated Time | Dependencies |
|------|---------------|----------------|--------------|
| 1.1 Echo MCP Server | Claude Code | 2h | None |
| 1.2 Byte-level Logging | Claude Code | 3h | None |
| 1.3 Process Monitoring | Claude Code | 2h | Task 1.1 |
| 2.1 Research SSE MCP | Claude Web | 1h | None |
| 2.2 SSE Bridge Mode | Claude Code | 4h | Task 2.1 |

### **Next Sprint Preparation**

| Task | AI Assignment | Estimated Time | Dependencies |
|------|---------------|----------------|--------------|
| 3.1 Choose REST API | Claude Web + Alex | 1h | None |
| 3.2 REST Adapter | Claude Code | 6h | Task 3.1 |
| 4.1 OpenAPI Interface | Claude Code | 8h | Working bridge |

---

## 🔄 Workflow Patterns

### **Research → Implementation Pattern**
```
1. Claude Web: Research options and best practices
2. Alex: Make strategic decision  
3. Claude Code: Implement solution
4. Alex: Test and validate
```

### **Debug → Fix Pattern**
```
1. Claude Code: Add detailed logging/monitoring
2. Alex: Run tests and collect data
3. Claude Code: Analyze logs and implement fix
4. Alex: Validate fix works
```

### **Design → Build Pattern**
```
1. Alex: Define requirements and constraints
2. Claude Code: Propose architecture
3. Alex: Review and approve approach
4. Claude Code: Implement with tests
```

---

## 🎯 Escalation Paths

### **When Claude Code Gets Stuck:**
- Switch to simpler approach or reduce scope
- Ask Claude Web for research on alternative patterns
- Break down into smaller, testable components
- Ask Alex for strategic direction change

### **When Research Needed:**
- Claude Web for external resources and examples
- Alex for internal system knowledge and constraints
- Community/Stack Overflow for specific technical issues

### **When Integration Issues:**
- Alex for system-specific knowledge and access
- Claude Code for bridging and adaptation patterns
- Specialized tools for testing and validation

---

## 📞 Communication Protocols

### **Status Updates:**
- **Daily**: Brief status on assigned tasks
- **Blockers**: Immediate escalation to Alex
- **Completion**: Summary with next steps

### **Handoffs:**
```
Claude Web → Alex → Claude Code
Research → Decision → Implementation
```

### **Documentation:**
- **Claude Code**: Technical implementation docs
- **Claude Web**: Research summaries and references  
- **Alex**: Strategic decisions and acceptance criteria

---

## 🎖️ Success Metrics

### **Claude Code Success:**
- ✅ Code compiles and passes tests
- ✅ Integration works end-to-end
- ✅ Performance meets requirements
- ✅ Documentation is clear and complete

### **Claude Web Success:**
- ✅ Research is comprehensive and current
- ✅ Options are clearly presented with pros/cons
- ✅ References are valid and accessible
- ✅ Recommendations are actionable

### **Overall Success:**
- ✅ Sprint goals achieved on time
- ✅ Quality maintained throughout development
- ✅ No major rework needed
- ✅ Foundation solid for next phase

---

**Ready to start? Let's begin with Task 1.1 - Claude Code will create the minimal echo MCP server!** 🚀