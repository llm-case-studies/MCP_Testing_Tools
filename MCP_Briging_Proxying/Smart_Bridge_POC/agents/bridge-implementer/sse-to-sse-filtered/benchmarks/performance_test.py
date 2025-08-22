#!/usr/bin/env python3
"""
Performance benchmarking for filtered SSE bridge
Tests latency impact and throughput with content filtering enabled/disabled
"""

import asyncio
import json
import time
import statistics
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from content_filters import ContentFilter, FilterConfig

@dataclass
class BenchmarkResult:
    """Results from a benchmark test"""
    test_name: str
    total_requests: int
    total_time: float
    avg_latency: float
    median_latency: float
    p95_latency: float
    p99_latency: float
    requests_per_second: float
    filter_overhead_percent: float

class PerformanceBenchmark:
    """Performance benchmarking tool for content filtering"""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        
    async def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all performance benchmarks"""
        print("Starting content filter performance benchmarks...")
        
        # Test scenarios
        scenarios = [
            ("baseline_no_filtering", self._test_baseline_no_filtering),
            ("default_filtering", self._test_default_filtering),
            ("strict_filtering", self._test_strict_filtering),
            ("pii_redaction_only", self._test_pii_redaction_only),
            ("html_sanitization_only", self._test_html_sanitization_only),
            ("large_content_filtering", self._test_large_content_filtering),
            ("high_frequency_filtering", self._test_high_frequency_filtering)
        ]
        
        for test_name, test_func in scenarios:
            print(f"\nRunning {test_name}...")
            result = await test_func()
            self.results.append(result)
            self._print_result(result)
            
        return self.results
        
    async def _test_baseline_no_filtering(self) -> BenchmarkResult:
        """Baseline test with no filtering"""
        return await self._run_filtering_benchmark(
            "baseline_no_filtering",
            FilterConfig(
                redact_emails=False,
                redact_phones=False,
                redact_ssns=False,
                redact_credit_cards=False,
                remove_scripts=False,
                remove_tracking=False,
                blocked_domains=[],
                blocked_keywords=[]
            ),
            self._generate_clean_messages(100)
        )
        
    async def _test_default_filtering(self) -> BenchmarkResult:
        """Test with default filtering configuration"""
        return await self._run_filtering_benchmark(
            "default_filtering",
            FilterConfig(),  # Default config
            self._generate_mixed_messages(100)
        )
        
    async def _test_strict_filtering(self) -> BenchmarkResult:
        """Test with strict filtering configuration"""
        return await self._run_filtering_benchmark(
            "strict_filtering",
            FilterConfig(
                blocked_domains=["malware.test.com", "ads.example.com", "tracking.com"],
                blocked_keywords=["malicious", "virus", "exploit", "phishing", "scam"],
                redact_emails=True,
                redact_phones=True,
                redact_ssns=True,
                redact_credit_cards=True,
                remove_scripts=True,
                remove_tracking=True,
                max_response_length=10000,
                summarize_threshold=3000
            ),
            self._generate_mixed_messages(100)
        )
        
    async def _test_pii_redaction_only(self) -> BenchmarkResult:
        """Test PII redaction performance in isolation"""
        return await self._run_filtering_benchmark(
            "pii_redaction_only",
            FilterConfig(
                redact_emails=True,
                redact_phones=True,
                redact_ssns=True,
                redact_credit_cards=True,
                # Disable other filtering
                remove_scripts=False,
                remove_tracking=False,
                blocked_domains=[],
                blocked_keywords=[]
            ),
            self._generate_pii_messages(100)
        )
        
    async def _test_html_sanitization_only(self) -> BenchmarkResult:
        """Test HTML sanitization performance in isolation"""
        return await self._run_filtering_benchmark(
            "html_sanitization_only",
            FilterConfig(
                remove_scripts=True,
                remove_tracking=True,
                normalize_whitespace=True,
                # Disable other filtering
                redact_emails=False,
                redact_phones=False,
                redact_ssns=False,
                redact_credit_cards=False,
                blocked_domains=[],
                blocked_keywords=[]
            ),
            self._generate_html_messages(100)
        )
        
    async def _test_large_content_filtering(self) -> BenchmarkResult:
        """Test filtering performance with large content"""
        return await self._run_filtering_benchmark(
            "large_content_filtering",
            FilterConfig(),
            self._generate_large_content_messages(50)  # Fewer messages due to size
        )
        
    async def _test_high_frequency_filtering(self) -> BenchmarkResult:
        """Test high-frequency message filtering"""
        return await self._run_filtering_benchmark(
            "high_frequency_filtering",
            FilterConfig(),
            self._generate_clean_messages(1000)  # High volume
        )
        
    async def _run_filtering_benchmark(
        self, 
        test_name: str, 
        config: FilterConfig, 
        messages: List[Dict[str, Any]]
    ) -> BenchmarkResult:
        """Run filtering benchmark for given configuration and messages"""
        
        filter_instance = ContentFilter(config)
        latencies: List[float] = []
        
        # Warm up
        for i in range(10):
            await filter_instance.filter_message(
                "server_to_client", "benchmark-session", messages[0]
            )
        
        # Actual benchmark
        start_time = time.time()
        
        for message in messages:
            message_start = time.perf_counter()
            await filter_instance.filter_message(
                "server_to_client", "benchmark-session", message
            )
            message_end = time.perf_counter()
            latencies.append((message_end - message_start) * 1000)  # Convert to ms
            
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        p95_latency = self._percentile(latencies, 95)
        p99_latency = self._percentile(latencies, 99)
        requests_per_second = len(messages) / total_time
        
        # Calculate overhead (compare to baseline if available)
        baseline_rps = self._get_baseline_rps()
        overhead_percent = ((baseline_rps - requests_per_second) / baseline_rps * 100) if baseline_rps else 0.0
        
        return BenchmarkResult(
            test_name=test_name,
            total_requests=len(messages),
            total_time=total_time,
            avg_latency=avg_latency,
            median_latency=median_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            requests_per_second=requests_per_second,
            filter_overhead_percent=overhead_percent
        )
        
    def _generate_clean_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate clean messages for testing"""
        messages = []
        for i in range(count):
            messages.append({
                "jsonrpc": "2.0",
                "id": f"clean-{i}",
                "result": {
                    "content": f"This is clean content message {i} with no issues.",
                    "metadata": {"url": f"https://example.com/page{i}"}
                }
            })
        return messages
        
    def _generate_mixed_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate mixed messages (clean and problematic)"""
        messages = []
        for i in range(count):
            if i % 4 == 0:
                # PII content
                messages.append({
                    "jsonrpc": "2.0",
                    "id": f"pii-{i}",
                    "result": {
                        "content": f"Contact: user{i}@example.com, Phone: (555) 123-{i:04d}",
                        "metadata": {"url": f"https://example.com/contact{i}"}
                    }
                })
            elif i % 4 == 1:
                # HTML content
                messages.append({
                    "jsonrpc": "2.0",
                    "id": f"html-{i}",
                    "result": {
                        "content": f"<div><script>alert('test')</script><p>Content {i}</p></div>",
                        "metadata": {"url": f"https://example.com/page{i}"}
                    }
                })
            elif i % 4 == 2:
                # Potentially blocked content
                messages.append({
                    "jsonrpc": "2.0",
                    "id": f"blocked-{i}",
                    "method": "tools/call",
                    "params": {
                        "name": "firecrawl_scrape",
                        "arguments": {"url": f"https://ads.example.com/page{i}"}
                    }
                })
            else:
                # Clean content
                messages.append({
                    "jsonrpc": "2.0",
                    "id": f"clean-{i}",
                    "result": {
                        "content": f"This is clean content message {i}.",
                        "metadata": {"url": f"https://example.com/page{i}"}
                    }
                })
        return messages
        
    def _generate_pii_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate messages with PII for redaction testing"""
        messages = []
        for i in range(count):
            messages.append({
                "jsonrpc": "2.0",
                "id": f"pii-{i}",
                "result": {
                    "content": f"""
                    Contact Information:
                    Email: user{i}@example.com
                    Phone: (555) 123-{i:04d}
                    SSN: 123-45-{i:04d}
                    Credit Card: 4111-1111-1111-{i:04d}
                    """,
                    "metadata": {"url": f"https://example.com/contact{i}"}
                }
            })
        return messages
        
    def _generate_html_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate messages with HTML content for sanitization testing"""
        messages = []
        for i in range(count):
            messages.append({
                "jsonrpc": "2.0",
                "id": f"html-{i}",
                "result": {
                    "content": f"""
                    <div>
                        <h1>Page {i}</h1>
                        <script>alert('XSS attempt {i}');</script>
                        <p onclick="malicious()">Click me</p>
                        <img src="tracking-pixel-{i}.gif" />
                        <style>body {{ background: red; }}</style>
                        <p>Regular content here for page {i}</p>
                    </div>
                    """,
                    "metadata": {"url": f"https://example.com/page{i}"}
                }
            })
        return messages
        
    def _generate_large_content_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate messages with large content for size management testing"""
        messages = []
        large_content = "This is a very long piece of content that will trigger summarization. " * 200
        
        for i in range(count):
            messages.append({
                "jsonrpc": "2.0",
                "id": f"large-{i}",
                "result": {
                    "content": f"Message {i}: {large_content}",
                    "metadata": {"url": f"https://example.com/article{i}"}
                }
            })
        return messages
        
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]
        
    def _get_baseline_rps(self) -> float:
        """Get baseline requests per second for overhead calculation"""
        for result in self.results:
            if result.test_name == "baseline_no_filtering":
                return result.requests_per_second
        return 0.0
        
    def _print_result(self, result: BenchmarkResult):
        """Print benchmark result"""
        print(f"  Total Requests: {result.total_requests}")
        print(f"  Total Time: {result.total_time:.2f}s")
        print(f"  Requests/sec: {result.requests_per_second:.1f}")
        print(f"  Avg Latency: {result.avg_latency:.2f}ms")
        print(f"  Median Latency: {result.median_latency:.2f}ms")
        print(f"  P95 Latency: {result.p95_latency:.2f}ms")
        print(f"  P99 Latency: {result.p99_latency:.2f}ms")
        if result.filter_overhead_percent > 0:
            print(f"  Filter Overhead: {result.filter_overhead_percent:.1f}%")
            
    def generate_report(self) -> str:
        """Generate comprehensive performance report"""
        report = []
        report.append("# Content Filter Performance Benchmark Report")
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary table
        report.append("## Summary")
        report.append("| Test Name | RPS | Avg Latency (ms) | P95 Latency (ms) | Overhead % |")
        report.append("|-----------|-----|------------------|------------------|------------|")
        
        for result in self.results:
            overhead_str = f"{result.filter_overhead_percent:.1f}%" if result.filter_overhead_percent > 0 else "N/A"
            report.append(f"| {result.test_name} | {result.requests_per_second:.1f} | "
                         f"{result.avg_latency:.2f} | {result.p95_latency:.2f} | {overhead_str} |")
        
        report.append("")
        
        # Detailed results
        report.append("## Detailed Results")
        for result in self.results:
            report.append(f"### {result.test_name}")
            report.append(f"- **Total Requests**: {result.total_requests}")
            report.append(f"- **Total Time**: {result.total_time:.2f}s")
            report.append(f"- **Requests per Second**: {result.requests_per_second:.1f}")
            report.append(f"- **Average Latency**: {result.avg_latency:.2f}ms")
            report.append(f"- **Median Latency**: {result.median_latency:.2f}ms")
            report.append(f"- **P95 Latency**: {result.p95_latency:.2f}ms")
            report.append(f"- **P99 Latency**: {result.p99_latency:.2f}ms")
            if result.filter_overhead_percent > 0:
                report.append(f"- **Filter Overhead**: {result.filter_overhead_percent:.1f}%")
            report.append("")
            
        # Performance analysis
        report.append("## Performance Analysis")
        
        baseline_result = next((r for r in self.results if r.test_name == "baseline_no_filtering"), None)
        if baseline_result:
            report.append(f"- **Baseline Performance**: {baseline_result.requests_per_second:.1f} RPS")
            
            # Find highest overhead
            max_overhead = max((r.filter_overhead_percent for r in self.results if r.filter_overhead_percent > 0), default=0)
            if max_overhead > 0:
                report.append(f"- **Maximum Overhead**: {max_overhead:.1f}%")
                
            # Performance recommendations
            if max_overhead > 20:
                report.append("- **⚠️ Warning**: Filter overhead exceeds 20%. Consider optimizing filter configuration.")
            elif max_overhead > 10:
                report.append("- **ℹ️ Info**: Filter overhead is moderate. Monitor in production.")
            else:
                report.append("- **✅ Good**: Filter overhead is within acceptable limits (<10%).")
                
        return "\n".join(report)

async def main():
    """Run performance benchmarks"""
    benchmark = PerformanceBenchmark()
    results = await benchmark.run_all_benchmarks()
    
    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK COMPLETE")
    print("="*80)
    
    # Generate and save report
    report = benchmark.generate_report()
    
    # Save to file
    report_path = os.path.join(os.path.dirname(__file__), "performance_report.md")
    with open(report_path, 'w') as f:
        f.write(report)
        
    print(f"\nDetailed report saved to: {report_path}")
    
    # Print summary
    baseline = next((r for r in results if r.test_name == "baseline_no_filtering"), None)
    if baseline:
        print(f"\nBaseline Performance: {baseline.requests_per_second:.1f} RPS")
        
        # Show overhead for each test
        for result in results:
            if result.test_name != "baseline_no_filtering" and result.filter_overhead_percent > 0:
                print(f"{result.test_name}: {result.filter_overhead_percent:.1f}% overhead")

if __name__ == "__main__":
    asyncio.run(main())