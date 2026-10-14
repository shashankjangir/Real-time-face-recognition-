"""
Utilities module for Real-Time Facial Recognition & Access System
CSV generation, analytics, performance metrics, and reporting functions.
"""

import csv
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np
import logging

import config
from database import get_db_manager

logger = logging.getLogger(__name__)

# ============================================================================
# CSV REPORT GENERATION
# ============================================================================

class ReportGenerator:
    """Generate various reports from recognition data."""

    def __init__(self, db_manager=None, reports_dir: str = config.REPORTS_DIR):
        self.db_manager = db_manager or get_db_manager()
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)

    def generate_access_log_report(self, start_date: str = None, end_date: str = None,
                                   person_name: str = None, filename: str = None) -> str:
        """
        Generate CSV report of access logs.

        Args:
            start_date: ISO format start date (default: 7 days ago)
            end_date: ISO format end date (default: now)
            person_name: Filter by person (optional)
            filename: Output filename (auto-generated if None)

        Returns:
            Path to generated CSV file
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()

        logs = self.db_manager.get_logs_by_date_range(start_date, end_date, name=person_name)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            person_filter = f"_{person_name}" if person_name else ""
            filename = f"access_log_{timestamp}{person_filter}.csv"

        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=config.CSV_REPORT_FIELDS, delimiter=config.CSV_DELIMITER)
            writer.writeheader()

            for log in logs:
                row = {
                    'timestamp': log['timestamp'],
                    'person_name': log['name'],
                    'confidence': round(log['confidence'], 3),
                    'identity_id': log.get('identity_id', '')
                }
                writer.writerow(row)

        logger.info(f"Generated access log report: {filepath} ({len(logs)} records)")
        return filepath

    def generate_enrolled_faces_report(self, filename: str = None) -> str:
        """
        Generate CSV report of all enrolled faces.

        Returns:
            Path to generated CSV file
        """
        identities = self.db_manager.get_all_identities()

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enrolled_faces_{timestamp}.csv"

        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name', 'quality_score'], delimiter=config.CSV_DELIMITER)
            writer.writeheader()

            for identity in identities:
                row = {
                    'id': identity['id'],
                    'name': identity['name'],
                    'quality_score': round(identity.get('quality_score', 0.0), 3)
                }
                writer.writerow(row)

        logger.info(f"Generated enrolled faces report: {filepath} ({len(identities)} identities)")
        return filepath

    def generate_daily_summary_report(self, date: str = None, filename: str = None) -> str:
        """
        Generate daily summary report of recognitions.

        Args:
            date: Date in YYYY-MM-DD format (default: today)
            filename: Output filename

        Returns:
            Path to generated CSV file
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        start_date = f"{date}T00:00:00"
        end_date = f"{date}T23:59:59"

        logs = self.db_manager.get_logs_by_date_range(start_date, end_date)

        # Aggregate by person
        summary = {}
        for log in logs:
            name = log['name']
            if name not in summary:
                summary[name] = {'count': 0, 'avg_confidence': 0.0, 'first_seen': log['timestamp'], 'last_seen': log['timestamp']}
            summary[name]['count'] += 1
            summary[name]['avg_confidence'] += log['confidence']
            summary[name]['last_seen'] = log['timestamp']

        # Calculate averages
        for name in summary:
            summary[name]['avg_confidence'] /= summary[name]['count']

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"daily_summary_{date}_{timestamp}.csv"

        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'person_name', 'count', 'avg_confidence', 'first_seen', 'last_seen'], delimiter=config.CSV_DELIMITER)
            writer.writeheader()

            for name, data in sorted(summary.items()):
                row = {
                    'date': date,
                    'person_name': name,
                    'count': data['count'],
                    'avg_confidence': round(data['avg_confidence'], 3),
                    'first_seen': data['first_seen'],
                    'last_seen': data['last_seen']
                }
                writer.writerow(row)

        logger.info(f"Generated daily summary report: {filepath}")
        return filepath

    def generate_confidence_distribution_report(self, hours: int = 24, filename: str = None) -> str:
        """
        Generate report of confidence score distribution.

        Returns:
            Path to generated CSV file
        """
        logs = self.db_manager.get_recent_logs(limit=10000, hours=hours)

        if not logs:
            logger.warning("No logs found for confidence distribution report")
            return None

        # Confidence bins: 0.5-0.6, 0.6-0.7, ..., 0.9-1.0
        bins = {
            '0.50-0.60': 0,
            '0.60-0.70': 0,
            '0.70-0.80': 0,
            '0.80-0.90': 0,
            '0.90-1.00': 0
        }

        for log in logs:
            confidence = log['confidence']
            if 0.50 <= confidence < 0.60:
                bins['0.50-0.60'] += 1
            elif 0.60 <= confidence < 0.70:
                bins['0.60-0.70'] += 1
            elif 0.70 <= confidence < 0.80:
                bins['0.70-0.80'] += 1
            elif 0.80 <= confidence < 0.90:
                bins['0.80-0.90'] += 1
            elif 0.90 <= confidence <= 1.00:
                bins['0.90-1.00'] += 1

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"confidence_distribution_{timestamp}.csv"

        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['confidence_range', 'count', 'percentage'], delimiter=config.CSV_DELIMITER)
            writer.writeheader()

            total = sum(bins.values())
            for range_label, count in sorted(bins.items()):
                percentage = round(100 * count / total, 1) if total > 0 else 0
                row = {
                    'confidence_range': range_label,
                    'count': count,
                    'percentage': f"{percentage}%"
                }
                writer.writerow(row)

        logger.info(f"Generated confidence distribution report: {filepath}")
        return filepath


# ============================================================================
# ANALYTICS FUNCTIONS
# ============================================================================

class Analytics:
    """Analytics and statistics computation."""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()

    def get_top_recognized_people(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """
        Get people with most recognitions in time window.

        Returns:
            List of dicts with person name and count
        """
        stats = self.db_manager.get_statistics(hours=hours)
        return stats.get('top_identities', [])[:limit]

    def get_hourly_traffic(self, date: str = None) -> Dict[str, int]:
        """
        Get recognition count by hour for a specific date.

        Returns:
            Dict mapping hour (00-23) to recognition count
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        start_date = f"{date}T00:00:00"
        end_date = f"{date}T23:59:59"

        logs = self.db_manager.get_logs_by_date_range(start_date, end_date)

        hourly = {f"{h:02d}:00": 0 for h in range(24)}

        for log in logs:
            timestamp = log['timestamp']
            hour = timestamp.split('T')[1].split(':')[0]
            key = f"{hour}:00"
            if key in hourly:
                hourly[key] += 1

        return hourly

    def get_accuracy_metrics(self, confidence_threshold: float = None) -> Dict:
        """
        Get system accuracy metrics.

        Args:
            confidence_threshold: Only count recognitions above this confidence

        Returns:
            Dict with various accuracy metrics
        """
        if confidence_threshold is None:
            confidence_threshold = config.LOG_CONFIDENCE_THRESHOLD

        logs = self.db_manager.get_recent_logs(limit=100000, hours=7*24)

        if not logs:
            return {'valid_recognitions': 0, 'total': 0, 'accuracy': 0.0}

        valid_count = sum(1 for log in logs if log['confidence'] >= confidence_threshold)
        total = len(logs)
        accuracy = valid_count / total if total > 0 else 0.0

        # Confidence statistics
        confidences = [log['confidence'] for log in logs]

        return {
            'valid_recognitions': valid_count,
            'total': total,
            'accuracy': round(accuracy, 3),
            'avg_confidence': round(np.mean(confidences), 3),
            'median_confidence': round(np.median(confidences), 3),
            'min_confidence': round(np.min(confidences), 3),
            'max_confidence': round(np.max(confidences), 3),
            'std_dev': round(np.std(confidences), 3)
        }

    def get_unique_people_count(self, hours: int = 24) -> int:
        """Get count of unique people recognized in time window."""
        stats = self.db_manager.get_statistics(hours=hours)
        return stats.get('unique_identities', 0)

    def get_false_positive_rate(self, confidence_threshold: float = None) -> float:
        """
        Estimate false positive rate (low confidence recognitions).

        This is approximate without ground truth labels.
        """
        if confidence_threshold is None:
            confidence_threshold = config.LOG_CONFIDENCE_THRESHOLD

        logs = self.db_manager.get_recent_logs(limit=10000, hours=24*7)
        if not logs:
            return 0.0

        low_conf = sum(1 for log in logs if log['confidence'] < confidence_threshold)
        return round(low_conf / len(logs), 3)

    def get_system_load(self) -> Dict:
        """Get current system load information."""
        try:
            db_manager = get_db_manager()
            stats = db_manager.get_statistics(hours=24)

            return {
                'total_recognitions': stats.get('total_recognitions', 0),
                'unique_identities': stats.get('unique_identities', 0),
                'avg_confidence': stats.get('avg_confidence', 0.0),
                'database_status': 'healthy'
            }
        except Exception as e:
            logger.error(f"Error getting system load: {e}")
            return {'database_status': 'error'}

    def export_analytics_json(self, hours: int = 24, filename: str = None) -> str:
        """
        Export comprehensive analytics as JSON.

        Returns:
            Path to generated JSON file
        """
        os.makedirs(config.REPORTS_DIR, exist_ok=True)

        analytics_data = {
            'timestamp': datetime.now().isoformat(),
            'time_window_hours': hours,
            'accuracy': self.get_accuracy_metrics(),
            'top_people': self.get_top_recognized_people(hours=hours),
            'unique_count': self.get_unique_people_count(hours=hours),
            'false_positive_rate': self.get_false_positive_rate(),
            'system_load': self.get_system_load()
        }

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analytics_{timestamp}.json"

        filepath = os.path.join(config.REPORTS_DIR, filename)

        with open(filepath, 'w') as f:
            json.dump(analytics_data, f, indent=2)

        logger.info(f"Exported analytics to: {filepath}")
        return filepath


# ============================================================================
# PERFORMANCE ANALYSIS
# ============================================================================

class PerformanceAnalyzer:
    """Analyze system performance metrics."""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()

    def get_performance_summary(self, hours: int = 24) -> Dict:
        """Get performance metrics summary."""
        metrics = self.db_manager.get_metrics_summary(hours=hours)
        return {
            'avg_frame_latency_ms': round(metrics.get('avg_frame_latency_ms', 0), 1),
            'max_frame_latency_ms': round(metrics.get('max_frame_latency_ms', 0), 1),
            'avg_fps': round(metrics.get('avg_fps', 0), 1),
            'min_fps': round(metrics.get('min_fps', 0), 1),
            'avg_memory_mb': round(metrics.get('avg_memory_mb', 0), 1),
            'target_latency_met': round(metrics.get('avg_frame_latency_ms', 0), 1) <= config.TARGET_LATENCY_MS,
            'target_fps_met': round(metrics.get('avg_fps', 0), 1) >= config.TARGET_FPS
        }

    def log_performance_status(self) -> str:
        """Generate performance status message."""
        summary = self.get_performance_summary()
        msg = f"Performance: {summary['avg_fps']} FPS (target: {config.TARGET_FPS}), "
        msg += f"Latency: {summary['avg_frame_latency_ms']}ms (target: {config.TARGET_LATENCY_MS}ms)"
        return msg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test report generation
    report_gen = ReportGenerator()
    print("Generating test reports...")
    print(f"  Access log: {report_gen.generate_access_log_report()}")
    print(f"  Enrolled faces: {report_gen.generate_enrolled_faces_report()}")
    print(f"  Daily summary: {report_gen.generate_daily_summary_report()}")
    print(f"  Confidence dist: {report_gen.generate_confidence_distribution_report()}")

    # Test analytics
    analytics = Analytics()
    accuracy = analytics.get_accuracy_metrics()
    print(f"\nAccuracy Metrics: {accuracy}")
