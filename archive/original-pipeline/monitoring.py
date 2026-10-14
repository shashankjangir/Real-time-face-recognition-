"""
Monitoring & Health Dashboard for Real-Time Facial Recognition System
Tracks performance, accuracy, and system health metrics.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

import config
from database import get_db_manager
from utils import Analytics, PerformanceAnalyzer

logger = logging.getLogger(__name__)

class HealthMonitor:
    """Comprehensive system health monitoring."""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        self.analytics = Analytics(self.db_manager)
        self.perf_analyzer = PerformanceAnalyzer(self.db_manager)
        self.health_history = []
        self.last_check = None

    def get_full_health_report(self) -> Dict:
        """Generate comprehensive health report."""
        now = datetime.now().isoformat()

        # Performance metrics
        perf_summary = self.perf_analyzer.get_performance_summary(hours=24)

        # Accuracy metrics
        accuracy = self.analytics.get_accuracy_metrics()

        # System load
        system_load = self.analytics.get_system_load()

        # Database status
        try:
            identities = self.db_manager.get_all_identities()
            db_status = 'healthy'
            db_records = len(identities)
        except Exception as e:
            logger.error(f"Database error: {e}")
            db_status = 'error'
            db_records = 0

        # Determine overall health
        overall_health = self._assess_health(perf_summary, accuracy, system_load, db_status)

        report = {
            'timestamp': now,
            'overall_status': overall_health['status'],
            'overall_health_score': overall_health['score'],
            'performance': {
                **perf_summary,
                'status': 'good' if perf_summary['target_fps_met'] and perf_summary['target_latency_met'] else 'degraded'
            },
            'accuracy': {
                **accuracy,
                'status': 'excellent' if accuracy['accuracy'] > 0.95 else 'good' if accuracy['accuracy'] > 0.85 else 'poor'
            },
            'database': {
                'status': db_status,
                'total_identities': db_records
            },
            'system_load': system_load,
            'recommendations': self._generate_recommendations(overall_health)
        }

        self.health_history.append(report)
        self.last_check = now

        return report

    def _assess_health(self, perf: Dict, accuracy: Dict, system_load: Dict, db_status: str) -> Dict:
        """Assess overall system health."""
        score = 100.0
        issues = []

        # Performance assessment (40% weight)
        if not perf['target_fps_met']:
            score -= 20
            issues.append(f"FPS below target: {perf['avg_fps']} < {config.TARGET_FPS}")
        if not perf['target_latency_met']:
            score -= 15
            issues.append(f"Latency above target: {perf['avg_frame_latency_ms']}ms > {config.TARGET_LATENCY_MS}ms")

        # Accuracy assessment (40% weight)
        if accuracy['accuracy'] < 0.85:
            score -= 30
            issues.append(f"Accuracy below 85%: {accuracy['accuracy']*100:.1f}%")
        elif accuracy['accuracy'] < 0.95:
            score -= 10
            issues.append(f"Accuracy below target 95%: {accuracy['accuracy']*100:.1f}%")

        # Database assessment (20% weight)
        if db_status != 'healthy':
            score -= 20
            issues.append("Database error")

        status = 'healthy' if score >= 90 else 'degraded' if score >= 70 else 'critical'

        return {
            'score': round(max(0, score), 1),
            'status': status,
            'issues': issues
        }

    def _generate_recommendations(self, health_report: Dict) -> List[str]:
        """Generate recommendations based on health status."""
        recommendations = []

        if 'FPS below target' in ' '.join(health_report['issues']):
            recommendations.append("Reduce processing resolution or increase frame skip to improve FPS")

        if 'Latency above target' in ' '.join(health_report['issues']):
            recommendations.append("Consider reducing image resolution or using fewer recognition workers")

        if 'Accuracy below' in ' '.join(health_report['issues']):
            recommendations.append("Adjust recognition threshold (lower = stricter matching)")
            recommendations.append("Ensure enrolled faces have high quality scores (>0.7)")
            recommendations.append("Improve lighting in recognition area")

        if health_report['score'] < 50:
            recommendations.append("System performance critical - investigate hardware/software issues")
            recommendations.append("Check CPU/memory usage on Raspberry Pi")
            recommendations.append("Verify database connectivity and performance")

        return recommendations

    def export_health_report(self, filename: str = None) -> str:
        """Export health report as JSON."""
        report = self.get_full_health_report()

        os.makedirs(config.REPORTS_DIR, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"health_report_{timestamp}.json"

        filepath = os.path.join(config.REPORTS_DIR, filename)

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Exported health report to: {filepath}")
        return filepath


class MetricsCollector:
    """Collect and aggregate system metrics over time."""

    def __init__(self, db_manager=None, collection_interval: int = 60):
        self.db_manager = db_manager or get_db_manager()
        self.collection_interval = collection_interval
        self.metrics_buffer = []
        self.last_collection = time.time()

    def should_collect(self) -> bool:
        """Check if it's time to collect metrics."""
        now = time.time()
        return (now - self.last_collection) >= self.collection_interval

    def collect_metrics(self, frame_latency_ms: float, fps: float, memory_mb: float,
                       queue_size: int, identities_count: int) -> None:
        """Collect current system metrics."""
        if not self.should_collect():
            return

        metric = {
            'timestamp': datetime.now().isoformat(),
            'frame_latency_ms': round(frame_latency_ms, 1),
            'fps': round(fps, 1),
            'memory_mb': round(memory_mb, 1),
            'queue_size': queue_size,
            'identities_count': identities_count
        }

        self.metrics_buffer.append(metric)
        self.last_collection = time.time()

        # Keep only last 1000 metrics in memory
        if len(self.metrics_buffer) > 1000:
            self.metrics_buffer = self.metrics_buffer[-1000:]

        # Also log to database
        try:
            self.db_manager.log_metrics(
                frame_latency_ms=frame_latency_ms,
                fps=fps,
                memory_mb=memory_mb,
                queue_size=queue_size,
                identities_count=identities_count
            )
        except Exception as e:
            logger.error(f"Failed to log metrics to database: {e}")

    def get_recent_metrics(self, minutes: int = 5) -> List[Dict]:
        """Get metrics from last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_buffer if datetime.fromisoformat(m['timestamp']) > cutoff]

    def get_metrics_summary(self, minutes: int = 5) -> Dict:
        """Get summarized metrics from recent period."""
        recent = self.get_recent_metrics(minutes=minutes)

        if not recent:
            return {}

        latencies = [m['frame_latency_ms'] for m in recent]
        fps_values = [m['fps'] for m in recent]
        memory_values = [m['memory_mb'] for m in recent]

        return {
            'collection_period_minutes': minutes,
            'samples': len(recent),
            'latency': {
                'avg': round(sum(latencies) / len(latencies), 1),
                'min': round(min(latencies), 1),
                'max': round(max(latencies), 1)
            },
            'fps': {
                'avg': round(sum(fps_values) / len(fps_values), 1),
                'min': round(min(fps_values), 1),
                'max': round(max(fps_values), 1)
            },
            'memory': {
                'avg': round(sum(memory_values) / len(memory_values), 1),
                'min': round(min(memory_values), 1),
                'max': round(max(memory_values), 1)
            }
        }


class PerformanceBenchmark:
    """Run performance benchmarks and optimization tests."""

    def __init__(self, recognition_engine):
        self.engine = recognition_engine

    def benchmark_recognition_latency(self, num_tests: int = 100) -> Dict:
        """
        Benchmark face recognition latency.
        Requires test image with faces loaded.
        """
        # This is a placeholder - actual benchmark needs test images
        logger.info(f"Benchmark not fully implemented - would run {num_tests} recognition tests")
        return {'status': 'benchmark_requires_test_images'}

    def benchmark_encoding_generation(self, num_faces: int = 10) -> Dict:
        """
        Benchmark encoding generation speed.
        """
        logger.info(f"Benchmark not fully implemented - would test {num_faces} face encodings")
        return {'status': 'benchmark_requires_test_images'}


class DashboardMetrics:
    """Metrics specifically for web dashboard display."""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        self.health_monitor = HealthMonitor(self.db_manager)
        self.metrics_collector = MetricsCollector(self.db_manager)

    def get_dashboard_data(self) -> Dict:
        """Get all data needed for dashboard rendering."""
        health = self.health_monitor.get_full_health_report()
        metrics = self.metrics_collector.get_metrics_summary(minutes=5)

        return {
            'timestamp': datetime.now().isoformat(),
            'health': {
                'overall': health['overall_status'],
                'score': health['overall_health_score'],
                'issues': health['recommendations'][:3]  # Top 3 issues
            },
            'performance': {
                'fps': health['performance']['avg_fps'],
                'fps_target': config.TARGET_FPS,
                'latency_ms': health['performance']['avg_frame_latency_ms'],
                'latency_target': config.TARGET_LATENCY_MS
            },
            'accuracy': {
                'score': health['accuracy']['accuracy'],
                'confidence_avg': health['accuracy']['avg_confidence'],
                'status': health['accuracy']['status']
            },
            'system': {
                'identities_enrolled': health['database']['total_identities'],
                'total_recognitions_24h': health['system_load']['total_recognitions'],
                'unique_people_24h': health['system_load']['unique_identities']
            }
        }


# Import os module for file operations
import os

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test health monitoring
    monitor = HealthMonitor()
    report = monitor.get_full_health_report()
    print(json.dumps(report, indent=2))
