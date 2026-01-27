import time
import functools
import logging
import psutil
import os
import streamlit as st
import pandas as pd
from typing import Optional, Any, List, Dict
from datetime import datetime

logger = logging.getLogger("PerformanceMonitor")

class PerformanceMonitor:
    """
    Centralized store for performance metrics.
    Persists logs in Streamlit Session State for UI display.
    """
    SESSION_KEY = "performance_metrics_log"

    @staticmethod
    def get_logs() -> List[Dict[str, Any]]:
        if PerformanceMonitor.SESSION_KEY not in st.session_state:
            st.session_state[PerformanceMonitor.SESSION_KEY] = []
        return st.session_state[PerformanceMonitor.SESSION_KEY]

    @staticmethod
    def log_event(operation: str, duration_sec: float, memory_delta_mb: float = 0.0, details: str = ""):
        entry = {
            "Timestamp": datetime.now().strftime("%H:%M:%S"),
            "Operation": operation,
            "Duration (s)": round(duration_sec, 4),
            "Memory Delta (MB)": round(memory_delta_mb, 2),
            "Details": details
        }

        # Add to Session State
        logs = PerformanceMonitor.get_logs()
        logs.insert(0, entry) # Prepend to show newest first
        # Keep buffer limited
        if len(logs) > 50:
            logs.pop()

        # Also log to standard Python logger
        logger.info(f"PERF | {operation} | {duration_sec:.4f}s | {memory_delta_mb:.2f}MB | {details}")

    @staticmethod
    def clear_logs():
        st.session_state[PerformanceMonitor.SESSION_KEY] = []

def get_process_memory_mb() -> float:
    """Returns current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def track_performance(operation_name: Optional[str] = None):
    """
    Decorator to track execution time and memory impact of a function.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            start_time = time.perf_counter()
            start_mem = get_process_memory_mb()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                end_mem = get_process_memory_mb()

                duration = end_time - start_time
                mem_delta = end_mem - start_mem

                PerformanceMonitor.log_event(op_name, duration, mem_delta)

        return wrapper
    return decorator

def get_dataframe_memory_usage(df: pd.DataFrame) -> float:
    """Returns deep memory usage of a DataFrame in MB."""
    if df is None or df.empty:
        return 0.0
    return df.memory_usage(deep=True).sum() / 1024 / 1024
