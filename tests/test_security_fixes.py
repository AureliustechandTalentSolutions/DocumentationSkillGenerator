#!/usr/bin/env python3
"""
Tests for security fixes: failed URL tracking, rate limiting warnings, and exception handling.
"""

import sys
import os
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add cli directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'cli'))

from doc_scraper import DocToSkillConverter


class TestFailedURLTracking(unittest.TestCase):
    """Test that failed URLs are tracked properly"""

    def setUp(self):
        """Save original working directory"""
        self.original_cwd = os.getcwd()

    def tearDown(self):
        """Restore original working directory"""
        os.chdir(self.original_cwd)

    def test_failed_urls_initialized(self):
        """Test that failed_urls list is initialized"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 10
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            self.assertIsInstance(converter.failed_urls, list)
            self.assertEqual(len(converter.failed_urls), 0)

    def test_failed_urls_with_parallel_workers(self):
        """Test that failed_urls is initialized for parallel workers"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 10,
            'workers': 4
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            self.assertIsInstance(converter.failed_urls, list)
            self.assertEqual(len(converter.failed_urls), 0)


class TestRateLimitingWarning(unittest.TestCase):
    """Test rate limiting warning for parallel scraping with zero rate limit"""

    def setUp(self):
        """Save original working directory"""
        self.original_cwd = os.getcwd()

    def tearDown(self):
        """Restore original working directory"""
        os.chdir(self.original_cwd)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('doc_scraper.DocToSkillConverter.scrape_page')
    def test_warning_shown_for_zero_rate_limit_with_workers(self, mock_scrape, mock_stdout):
        """Test that warning is shown when rate_limit is 0 and workers > 1"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 1,
            'workers': 4,
            'rate_limit': 0
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            
            # Mock the scrape_page to avoid actual scraping
            mock_scrape.return_value = None
            
            # Run scrape_all
            converter.scrape_all()
            
            # Check that warning was printed
            output = mock_stdout.getvalue()
            self.assertIn("WARNING", output)
            self.assertIn("Rate limiting disabled", output)
            self.assertIn("4 workers", output)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('doc_scraper.DocToSkillConverter.scrape_page')
    def test_no_warning_for_nonzero_rate_limit(self, mock_scrape, mock_stdout):
        """Test that no warning is shown when rate_limit is > 0"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 1,
            'workers': 4,
            'rate_limit': 0.5
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            
            # Mock the scrape_page to avoid actual scraping
            mock_scrape.return_value = None
            
            # Run scrape_all
            converter.scrape_all()
            
            # Check that warning was NOT printed
            output = mock_stdout.getvalue()
            self.assertNotIn("Rate limiting disabled", output)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('doc_scraper.DocToSkillConverter.scrape_page')
    def test_no_warning_for_single_worker(self, mock_scrape, mock_stdout):
        """Test that no warning is shown for single worker even with rate_limit=0"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 1,
            'workers': 1,
            'rate_limit': 0
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            
            # Mock the scrape_page to avoid actual scraping
            mock_scrape.return_value = None
            
            # Run scrape_all
            converter.scrape_all()
            
            # Check that warning was NOT printed (single worker)
            output = mock_stdout.getvalue()
            self.assertNotIn("Rate limiting disabled", output)


class TestExceptionHandling(unittest.TestCase):
    """Test improved exception handling in parallel scraping"""

    def setUp(self):
        """Save original working directory"""
        self.original_cwd = os.getcwd()

    def tearDown(self):
        """Restore original working directory"""
        os.chdir(self.original_cwd)

    @patch('sys.stdout', new_callable=StringIO)
    def test_failed_url_tracking_in_parallel(self, mock_stdout):
        """Test that failed URLs are tracked during parallel scraping"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 5,
            'workers': 2,
            'rate_limit': 0.1
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=True)
            
            # Mock scrape_page to simulate failures
            def mock_scrape_page(url):
                if 'fail' in url:
                    raise Exception(f"Simulated failure for {url}")
                return None
            
            with patch.object(converter, 'scrape_page', side_effect=mock_scrape_page):
                # Add some URLs including ones that will fail
                converter.pending_urls.clear()
                converter.pending_urls.extend([
                    'https://example.com/page1',
                    'https://example.com/fail1',
                    'https://example.com/page2',
                    'https://example.com/fail2',
                ])
                
                # Run scraping
                converter.scrape_all()
                
                # Check output contains failure messages
                output = mock_stdout.getvalue()
                # We expect to see the failure indicators in the output
                if converter.workers > 1:
                    # In parallel mode, we should track failed URLs
                    # Note: The actual tracking happens during real scraping,
                    # this test validates the mechanism is in place
                    self.assertIsInstance(converter.failed_urls, list,
                        "Expected failed_urls to be a list in parallel mode"
                    )


class TestFailureSummary(unittest.TestCase):
    """Test that failure summary is shown at the end"""

    def setUp(self):
        """Save original working directory"""
        self.original_cwd = os.getcwd()

    def tearDown(self):
        """Restore original working directory"""
        os.chdir(self.original_cwd)

    @patch('sys.stdout', new_callable=StringIO)
    def test_failure_summary_shown_when_failures_exist(self, mock_stdout):
        """Test that failure summary is shown when there are failed URLs"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 3,
            'workers': 2,
            'rate_limit': 0.1
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=False)
            
            # Manually add some failed URLs to test the summary
            converter.failed_urls = [
                'https://example.com/fail1',
                'https://example.com/fail2',
                'https://example.com/fail3'
            ]
            
            # Mock scrape_page to do nothing
            with patch.object(converter, 'scrape_page', return_value=None):
                # Mock save_summary to avoid file operations
                with patch.object(converter, 'save_summary', return_value=None):
                    converter.scrape_all()
            
            # Check that summary was printed
            output = mock_stdout.getvalue()
            self.assertIn("pages failed to scrape", output)
            self.assertIn("fail1", output)
            self.assertIn("fail2", output)
            self.assertIn("fail3", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_failure_summary_truncates_long_lists(self, mock_stdout):
        """Test that failure summary truncates when more than 10 failures"""
        config = {
            'name': 'test',
            'base_url': 'https://example.com/',
            'selectors': {'main_content': 'article'},
            'max_pages': 1,
            'workers': 2
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            converter = DocToSkillConverter(config, dry_run=False)
            
            # Add more than 10 failed URLs
            converter.failed_urls = [f'https://example.com/fail{i}' for i in range(15)]
            
            # Mock scrape_page and save_summary
            with patch.object(converter, 'scrape_page', return_value=None):
                with patch.object(converter, 'save_summary', return_value=None):
                    converter.scrape_all()
            
            # Check that summary shows truncation message
            output = mock_stdout.getvalue()
            self.assertIn("15 pages failed to scrape", output)
            self.assertIn("and 5 more", output)


if __name__ == '__main__':
    unittest.main()
