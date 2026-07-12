"""Tests for profiling utilities."""

import logging
import re
import time

from voice_to_text.profiling import Profiler, create_profiler


def set_profiling_log_level(level=logging.INFO):
    """Set the log level for the profiling logger."""
    logging.getLogger("voice_to_text.profiling").setLevel(level)


class TestProfiler:
    """Test Profiler class behavior at different granularity levels."""

    def test_profiler_off_no_overhead(self, caplog):
        """When profiling=off, no logging occurs and methods return immediately."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "off"}
        profiler = Profiler(config)

        profiler.start()
        profiler.phase("test_phase")
        total = profiler.finish()

        assert total == 0.0
        # No PROFIL logs should appear
        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 0

    def test_profiler_off_section_context_manager(self, caplog):
        """Section context manager yields immediately when profiling=off."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "off"}
        profiler = Profiler(config)

        with profiler.section("test_section"):
            time.sleep(0.01)  # Should not be timed

        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 0

    def test_profiler_basic_logs_total_only(self, caplog):
        """Basic mode logs only total processing time at finish."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "basic"}
        profiler = Profiler(config)

        profiler.start()
        time.sleep(0.01)
        profiler.phase("some_phase")  # Should not log in basic mode
        time.sleep(0.01)
        total = profiler.finish()

        assert total > 0.0
        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 1
        assert "Total processing time:" in profil_logs[0].getMessage()

    def test_profiler_basic_section_no_log(self, caplog):
        """Section context manager doesn't log in basic mode."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "basic"}
        profiler = Profiler(config)

        profiler.start()
        with profiler.section("test_section"):
            time.sleep(0.01)
        profiler.finish()

        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 1
        assert "Total processing time:" in profil_logs[0].getMessage()

    def test_profiler_detailed_logs_all_phases(self, caplog):
        """Detailed mode logs each phase with delta and total."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "detailed"}
        profiler = Profiler(config)

        profiler.start()
        time.sleep(0.01)
        profiler.phase("phase1")
        time.sleep(0.01)
        profiler.phase("phase2")
        total = profiler.finish()

        assert total > 0.0
        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        # Should have: phase1, phase2, total_processing_time
        assert len(profil_logs) == 3
        # Check phase format: "[PROFIL] phase1: +X.XXXs (total Y.YYYs)"
        for log in profil_logs[:2]:  # First two are phases
            msg = log.getMessage()
            assert "[PROFIL]" in msg
            assert "+" in msg
            assert "total" in msg
        # Final total has different format: "[PROFIL] total_processing_time: X.XXXs"
        assert "total_processing_time" in profil_logs[2].getMessage()

    def test_profiler_detailed_section_logs_on_exit(self, caplog):
        """Section context manager logs phase on exit in detailed mode."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "detailed"}
        profiler = Profiler(config)

        profiler.start()
        with profiler.section("my_section"):
            time.sleep(0.01)
        profiler.finish()

        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        # Should have: my_section, total_processing_time
        assert len(profil_logs) == 2
        assert "my_section" in profil_logs[0].getMessage()

    def test_profiler_defaults_to_off(self, caplog):
        """Profiler defaults to 'off' when config missing profiling key."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        profiler = Profiler({})  # No profiling key

        profiler.start()
        profiler.phase("test")
        total = profiler.finish()

        # When off, total should be 0.0 (or very close to 0)
        assert total < 0.001  # Allow tiny epsilon
        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 0

    def test_create_profiler_factory(self):
        """Factory function creates Profiler instance."""
        profiler = create_profiler({"profiling": "detailed"})
        assert isinstance(profiler, Profiler)
        assert profiler._detailed is True

    def test_profiler_exception_handling_in_section(self, caplog):
        """Section logs phase even if exception occurs inside."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "detailed"}
        profiler = Profiler(config)

        profiler.start()
        try:
            with profiler.section("failing_section"):
                raise ValueError("test error")
        except ValueError:
            pass
        profiler.finish()

        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        assert len(profil_logs) == 2
        assert "failing_section" in profil_logs[0].getMessage()


class TestProfilerIntegration:
    """Integration tests for profiler with realistic timing."""

    def test_sequential_phases_timing(self, caplog):
        """Multiple sequential phases show increasing totals."""
        set_profiling_log_level()
        caplog.set_level(logging.INFO, logger="voice_to_text.profiling")
        config = {"profiling": "detailed"}
        profiler = Profiler(config)

        profiler.start()
        time.sleep(0.01)
        profiler.phase("phase1")
        time.sleep(0.01)
        profiler.phase("phase2")
        time.sleep(0.01)
        profiler.phase("phase3")
        profiler.finish()

        profil_logs = [r for r in caplog.records if "[PROFIL]" in r.getMessage()]
        # Extract totals from each log
        totals = []
        for log in profil_logs:
            msg = log.getMessage()
            # Parse "total X.XXXs" from phase logs, or "X.XXXs" from final total
            match = re.search(r"total ([\d.]+)s", msg)
            if not match:
                # Try final total format: "total_processing_time: X.XXXs"
                match = re.search(r"total_processing_time: ([\d.]+)s", msg)
            if match:
                totals.append(float(match.group(1)))

        # Totals should be monotonically increasing
        assert len(totals) == 4  # 3 phases + final total
        # Allow for very small time differences between last phase and finish()
        assert totals[0] < totals[1] < totals[2] <= totals[3]
