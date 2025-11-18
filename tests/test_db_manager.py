import unittest
from unittest import mock
import sqlite3
from datetime import datetime, timedelta
import os
import sys
from contextlib import contextmanager

# Add the parent directory to the path to find the database module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_manager import get_previous_day_image, init_db, open_db, get_create_table_queries

class TestDbManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary in-memory database for testing."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        for query in get_create_table_queries():
            self.conn.execute(query)

        today = datetime.now()
        yesterday = today - timedelta(days=1)

        self.today_str = today.strftime('%Y%m%d')
        self.yesterday_str = yesterday.strftime('%Y%m%d')

        self.layer_id = 1
        self.current_image_path = f"plant_images/layer_1/{self.today_str}_120000.jpg"
        self.previous_day_image_path_latest = f"plant_images/layer_1/{self.yesterday_str}_180000.jpg"

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    @mock.patch('database.db_manager.open_db')
    def test_get_previous_day_image(self, mock_open_db):
        """Test that get_previous_day_image returns the correct image path."""

        @contextmanager
        def db_context_manager(db_path=None):
            yield self.conn

        mock_open_db.side_effect = db_context_manager

        # Insert test data
        yesterday = datetime.now() - timedelta(days=1)
        self.conn.execute(
            "INSERT INTO ai_reports (layer_id, timestamp, image_path, last_updated) VALUES (?, ?, ?, ?)",
            (self.layer_id, yesterday.replace(hour=9).isoformat(), f"plant_images/layer_1/{self.yesterday_str}_090000.jpg", yesterday.isoformat())
        )
        self.conn.execute(
            "INSERT INTO ai_reports (layer_id, timestamp, image_path, last_updated) VALUES (?, ?, ?, ?)",
            (self.layer_id, yesterday.replace(hour=18).isoformat(), self.previous_day_image_path_latest, yesterday.isoformat())
        )
        self.conn.commit()

        image_path = get_previous_day_image(self.layer_id, self.current_image_path)
        self.assertEqual(image_path, self.previous_day_image_path_latest)

    @mock.patch('database.db_manager.open_db')
    def test_get_previous_day_image_no_image(self, mock_open_db):
        """Test that get_previous_day_image returns None when no image is found."""
        @contextmanager
        def db_context_manager(db_path=None):
            yield self.conn

        mock_open_db.side_effect = db_context_manager

        image_path = get_previous_day_image(self.layer_id, self.current_image_path)
        self.assertIsNone(image_path)

if __name__ == '__main__':
    unittest.main()
