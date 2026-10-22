"""
Utilities Module for Real-Time Facial Recognition & Access System
Dynamic CSV report generation, audit trail exports, and system analytics.
"""

import os
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import logging

try:
    from . import config
    from .database import get_db_manager, DatabaseManager
except (ImportError, ValueError):
    import config
    from database import get_db_manager, DatabaseManager

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Dynamic CSV report generator for audit trails, compliance, and attendance logging.
    """

    def __init__(self, db_manager: DatabaseManager = None, reports_dir: str = config.REPORTS_DIR):
        self.db_manager = db_manager or get_db_manager()
        self.reports_dir = str(reports_dir)
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_access_log_csv(self, start_date: str = None, end_date: str = None,
                                person_name: str = None, status: str = None,
                                min_confidence: float = 0.0,
                                filename: str = None) -> Tuple[str, str]:
        """
        Dynamically generate CSV report filtered by date range and identity.
        Returns: (file_path, csv_content_string)
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()

        logs = self.db_manager.get_logs_by_date_range(
            start_date=start_date,
            end_date=end_date,
            name=person_name,
            status=status,
            min_confidence=min_confidence
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=config.CSV_DELIMITER)

        # Header metadata block
        writer.writerow(["# REAL-TIME FACIAL RECOGNITION ACCESS SYSTEM - TRANSACTION AUDIT REPORT"])
        writer.writerow(["# Generated At", datetime.now().strftime(config.CSV_DATE_FORMAT)])
        writer.writerow(["# Date Filter", f"{start_date} to {end_date}"])
        writer.writerow(["# Person Filter", person_name or "ALL"])
        writer.writerow(["# Records Found", len(logs)])
        writer.writerow([])  # blank line separator

        # Column headers
        writer.writerow(["Timestamp", "Person Name", "Status", "Confidence", "Match Distance", "Identity ID", "Detection Model", "Decision", "Reason", "Action Outcome", "Action Detail"])

        # Data rows
        for item in logs:
            writer.writerow([
                item.get('timestamp', ''),
                item.get('name', 'Unknown'),
                item.get('status', 'unknown'),
                f"{float(item.get('confidence', 0.0)):.3f}",
                f"{float(item.get('match_distance', 0.0)):.3f}",
                item.get('identity_id', '') or '',
                item.get('detection_model', 'hog'),
                item.get('decision', ''), item.get('reason', ''),
                item.get('action_outcome', ''), item.get('action_detail', '')
            ])

        content = buffer.getvalue()

        # Save to disk
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = f"_{person_name}" if person_name else ""
            filename = f"access_audit_{ts}{suffix}.csv"

        filepath = os.path.join(self.reports_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Generated CSV report: {filepath} with {len(logs)} records.")
        return filepath, content

    def generate_daily_summary_csv(self, date_str: str = None, filename: str = None) -> Tuple[str, str]:
        """Generate aggregated daily summary (first in, last out, total transactions)."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        start = f"{date_str}T00:00:00"
        end = f"{date_str}T23:59:59"
        logs = self.db_manager.get_logs_by_date_range(start, end, status='verified')

        # Group by name
        grouped: Dict[str, List[Dict]] = {}
        for row in logs:
            name = row['name']
            grouped.setdefault(name, []).append(row)

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=config.CSV_DELIMITER)
        writer.writerow(["# DAILY ACCESS SUMMARY", date_str])
        writer.writerow(["Person Name", "Total Authentications", "First Entry Time", "Last Entry Time", "Avg Confidence"])

        for name, records in sorted(grouped.items()):
            records.sort(key=lambda r: r['timestamp'])
            first_t = records[0]['timestamp']
            last_t = records[-1]['timestamp']
            avg_c = sum(float(r['confidence']) for r in records) / len(records)
            writer.writerow([name, len(records), first_t, last_t, f"{avg_c:.3f}"])

        content = buffer.getvalue()
        if not filename:
            filename = f"daily_summary_{date_str.replace('-', '')}.csv"
        filepath = os.path.join(self.reports_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            f.write(content)

        return filepath, content


class Analytics:
    """Computes traffic metrics, confidence distributions, and accuracy statistics."""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or get_db_manager()

    def get_hourly_activity(self, hours: int = 24) -> Dict[str, int]:
        logs = self.db_manager.get_recent_logs(limit=1000, hours=hours)
        hourly: Dict[str, int] = {f"{h:02d}:00": 0 for h in range(24)}
        for row in logs:
            try:
                dt = datetime.fromisoformat(row['timestamp'])
                key = f"{dt.hour:02d}:00"
                hourly[key] = hourly.get(key, 0) + 1
            except Exception:
                pass
        return hourly

    def get_top_identities(self, limit: int = 5, hours: int = 24) -> List[Dict[str, Any]]:
        logs = self.db_manager.get_recent_logs(limit=1000, hours=hours)
        counts: Dict[str, int] = {}
        for row in logs:
            if row.get('status') == 'verified':
                name = row.get('name', 'Unknown')
                counts[name] = counts.get(name, 0) + 1

        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"name": name, "count": count} for name, count in sorted_items]
