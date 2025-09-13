# pydantree/core/profiler.py
from __future__ import annotations

import time
import threading
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, ContextManager
from contextlib import contextmanager
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json

from pydantic import BaseModel, Field


@dataclass
class MemorySnapshot:
    """Memory usage snapshot at a point in time."""
    timestamp: float
    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""
    operation: str
    duration: float
    memory_delta: float
    thread_id: int
    timestamp: float


class PerformanceProfiler:
    """High-performance profiler with memory tracking and insights."""
    
    def __init__(self, enabled: bool = True, track_memory: bool = True, max_history: int = 10000):
        self.enabled = enabled
        self.track_memory = track_memory
        self.max_history = max_history
        
        # Thread-safe storage
        self._metrics: deque[PerformanceMetric] = deque(maxlen=max_history)
        self._memory_snapshots: deque[MemorySnapshot] = deque(maxlen=1000)
        self._operation_stack: Dict[int, List[tuple[str, float, float]]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # Process handle for memory monitoring
        self._process = psutil.Process() if track_memory else None
        self._baseline_memory = self._get_memory_info() if track_memory else None
        
        # Aggregated statistics
        self._operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0, 'total_time': 0.0, 'min_time': float('inf'), 
            'max_time': 0.0, 'memory_delta': 0.0
        })
    
    @contextmanager
    def profile(self, operation: str) -> ContextManager[None]:
        """Context manager for profiling code blocks."""
        if not self.enabled:
            yield
            return
        
        thread_id = threading.get_ident()
        start_time = time.perf_counter()
        start_memory = self._get_memory_info() if self.track_memory else 0.0
        
        with self._lock:
            self._operation_stack[thread_id].append((operation, start_time, start_memory))
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = self._get_memory_info() if self.track_memory else 0.0
            
            with self._lock:
                if self._operation_stack[thread_id]:
                    op_name, op_start, op_memory = self._operation_stack[thread_id].pop()
                    duration = end_time - op_start
                    memory_delta = end_memory - op_memory if self.track_memory else 0.0
                    
                    # Store metric
                    metric = PerformanceMetric(
                        operation=op_name,
                        duration=duration,
                        memory_delta=memory_delta,
                        thread_id=thread_id,
                        timestamp=end_time
                    )
                    self._metrics.append(metric)
                    
                    # Update aggregated stats
                    stats = self._operation_stats[op_name]
                    stats['count'] += 1
                    stats['total_time'] += duration
                    stats['min_time'] = min(stats['min_time'], duration)
                    stats['max_time'] = max(stats['max_time'], duration)
                    stats['memory_delta'] += memory_delta
                    
                    # Store memory snapshot periodically
                    if self.track_memory and len(self._memory_snapshots) == 0 or \
                       (self._memory_snapshots and end_time - self._memory_snapshots[-1].timestamp > 1.0):
                        self._memory_snapshots.append(self._create_memory_snapshot(end_time))
    
    def _get_memory_info(self) -> float:
        """Get current memory usage in MB."""
        if not self._process:
            return 0.0
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    
    def _create_memory_snapshot(self, timestamp: float) -> MemorySnapshot:
        """Create memory snapshot at given timestamp."""
        memory_info = self._process.memory_info()
        virtual_memory = psutil.virtual_memory()
        
        return MemorySnapshot(
            timestamp=timestamp,
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            percent=self._process.memory_percent(),
            available_mb=virtual_memory.available / 1024 / 1024
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary with key insights."""
        with self._lock:
            if not self._metrics:
                return {'status': 'no_data', 'enabled': self.enabled}
            
            total_time = sum(m.duration for m in self._metrics)
            memory_stats = self._get_memory_stats()
            
            # Find slowest operations
            sorted_ops = sorted(
                self._operation_stats.items(),
                key=lambda x: x[1]['total_time'],
                reverse=True
            )
            
            return {
                'status': 'active',
                'enabled': self.enabled,
                'total_operations': len(self._metrics),
                'total_time': total_time,
                'unique_operations': len(self._operation_stats),
                'memory_stats': memory_stats,
                'top_operations': dict(sorted_ops[:5]),
                'insights': self._generate_insights()
            }
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        with self._lock:
            summary = self.get_summary()
            
            detailed_metrics = []
            for op_name, stats in self._operation_stats.items():
                avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
                detailed_metrics.append({
                    'operation': op_name,
                    'count': stats['count'],
                    'total_time': f"{stats['total_time']:.3f}s",
                    'avg_time': f"{avg_time:.3f}s",
                    'min_time': f"{stats['min_time']:.3f}s",
                    'max_time': f"{stats['max_time']:.3f}s",
                    'memory_delta': f"{stats['memory_delta']:.1f}MB"
                })
            
            # Sort by total time
            detailed_metrics.sort(key=lambda x: float(x['total_time'][:-1]), reverse=True)
            
            return {
                'summary': summary,
                'detailed_metrics': detailed_metrics,
                'memory_timeline': [
                    {
                        'timestamp': snap.timestamp,
                        'rss_mb': snap.rss_mb,
                        'percent': snap.percent
                    }
                    for snap in list(self._memory_snapshots)[-20:]  # Last 20 snapshots
                ],
                'thread_breakdown': self._get_thread_breakdown()
            }
    
    def _get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        if not self.track_memory or not self._memory_snapshots:
            return {'tracking_enabled': False}
        
        snapshots = list(self._memory_snapshots)
        current = snapshots[-1] if snapshots else None
        peak = max(snapshots, key=lambda s: s.rss_mb) if snapshots else None
        
        return {
            'tracking_enabled': True,
            'current_mb': current.rss_mb if current else 0,
            'peak_mb': peak.rss_mb if peak else 0,
            'baseline_mb': self._baseline_memory if self._baseline_memory else 0,
            'delta_mb': (current.rss_mb - self._baseline_memory) if current and self._baseline_memory else 0
        }
    
    def _get_thread_breakdown(self) -> Dict[str, Any]:
        """Get performance breakdown by thread."""
        thread_stats = defaultdict(lambda: {'operations': 0, 'total_time': 0.0})
        
        for metric in self._metrics:
            stats = thread_stats[metric.thread_id]
            stats['operations'] += 1
            stats['total_time'] += metric.duration
        
        return dict(thread_stats)
    
    def _generate_insights(self) -> List[str]:
        """Generate performance insights and recommendations."""
        insights = []
        
        if not self._operation_stats:
            return ["No operations profiled yet"]
        
        # Find slowest operation
        slowest_op = max(self._operation_stats.items(), key=lambda x: x[1]['total_time'])
        total_time = sum(stats['total_time'] for stats in self._operation_stats.values())
        
        if slowest_op[1]['total_time'] > total_time * 0.5:
            insights.append(f"Operation '{slowest_op[0]}' accounts for {slowest_op[1]['total_time']/total_time*100:.1f}% of total time")
        
        # Memory insights
        if self.track_memory and self._memory_snapshots:
            memory_growth = self._memory_snapshots[-1].rss_mb - self._memory_snapshots[0].rss_mb
            if memory_growth > 100:  # More than 100MB growth
                insights.append(f"Memory usage increased by {memory_growth:.1f}MB during profiling")
        
        # Thread efficiency
        thread_count = len(self._get_thread_breakdown())
        if thread_count > 1:
            insights.append(f"Multi-threaded execution detected ({thread_count} threads)")
        
        return insights
    
    def save_report(self, output_path: Path) -> None:
        """Save detailed report to file."""
        report = self.get_detailed_report()
        
        if output_path.suffix == '.json':
            with output_path.open('w') as f:
                json.dump(report, f, indent=2, default=str)
        else:
            # Text format
            with output_path.open('w') as f:
                f.write("Pydantree Performance Report\n")
                f.write("=" * 30 + "\n\n")
                
                summary = report['summary']
                f.write(f"Total Operations: {summary['total_operations']}\n")
                f.write(f"Total Time: {summary['total_time']:.3f}s\n")
                f.write(f"Memory Peak: {summary['memory_stats']['peak_mb']:.1f}MB\n\n")
                
                f.write("Top Operations:\n")
                for metric in report['detailed_metrics'][:10]:
                    f.write(f"  {metric['operation']}: {metric['total_time']} ({metric['count']} calls)\n")
    
    def compare_with_baseline(self, baseline_path: Path) -> Dict[str, Any]:
        """Compare current performance with baseline."""
        try:
            with baseline_path.open() as f:
                baseline = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'error': 'Could not load baseline file'}
        
        current = self.get_detailed_report()
        comparison = {
            'baseline_file': str(baseline_path),
            'performance_changes': {},
            'overall_assessment': 'stable'
        }
        
        # Compare operation times
        baseline_ops = {m['operation']: float(m['total_time'][:-1]) for m in baseline.get('detailed_metrics', [])}
        current_ops = {m['operation']: float(m['total_time'][:-1]) for m in current.get('detailed_metrics', [])}
        
        significant_changes = 0
        for op_name in set(baseline_ops.keys()) & set(current_ops.keys()):
            baseline_time = baseline_ops[op_name]
            current_time = current_ops[op_name]
            
            if baseline_time > 0:
                change_percent = ((current_time - baseline_time) / baseline_time) * 100
                if abs(change_percent) > 10:  # More than 10% change
                    comparison['performance_changes'][op_name] = {
                        'change_percent': f"{change_percent:+.1f}%",
                        'baseline_time': f"{baseline_time:.3f}s",
                        'current_time': f"{current_time:.3f}s",
                        'status': 'regression' if change_percent > 0 else 'improvement'
                    }
                    significant_changes += 1
        
        # Overall assessment
        if significant_changes > 0:
            regressions = sum(1 for change in comparison['performance_changes'].values() 
                            if change['status'] == 'regression')
            if regressions > significant_changes / 2:
                comparison['overall_assessment'] = 'performance_regression'
            else:
                comparison['overall_assessment'] = 'performance_improvement'
        
        return comparison
    
    def reset(self) -> None:
        """Reset all profiling data."""
        with self._lock:
            self._metrics.clear()
            self._memory_snapshots.clear()
            self._operation_stack.clear()
            self._operation_stats.clear()
            if self.track_memory:
                self._baseline_memory = self._get_memory_info()
    
    def enable(self) -> None:
        """Enable profiling."""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable profiling."""
        self.enabled = False
