from prometheus_client import Counter, Histogram, Gauge

DOWNLOAD_REQUESTS_TOTAL = Counter(
    "bot_download_requests_total",
    "Total download attempts",
    ["platform", "status"]
)


DOWNLOAD_DURATION_SECONDS = Histogram(
    "bot_download_duration_seconds",
    "Time spent downloading media in seconds",
    ["platform"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0)
)


DOWNLOADED_BYTES_TOTAL = Counter(
    "bot_downloaded_bytes_total",
    "Total volume of downloaded media in bytes",
    ["platform"]
)

ACTIVE_DOWNLOADS = Gauge(
    "bot_active_downloads",
    "Number of currently active download tasks",
    ["platform"]
)