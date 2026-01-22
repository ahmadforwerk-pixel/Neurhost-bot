"""Time formatting utilities."""


def seconds_to_human(seconds: int) -> str:
    """
    Convert seconds to human-readable format.
    
    Args:
        seconds: Number of seconds
    
    Returns:
        Formatted string (e.g., "5d 3h 2m 1s")
    
    Examples:
        >>> seconds_to_human(3661)
        '1h 1m 1s'
        >>> seconds_to_human(86400)
        '1d'
    """
    if seconds is None or seconds < 0:
        return "0s"
    
    seconds = int(seconds)
    
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def render_bar(percent: float, length: int = 12) -> str:
    """
    Render a progress bar.
    
    Args:
        percent: Percentage (0-100)
        length: Bar length in characters
    
    Returns:
        Progress bar string
    
    Examples:
        >>> render_bar(50)
        '██████░░░░░░ 50%'
    """
    try:
        p = max(0, min(100, int(percent)))
    except Exception:
        p = 0
    
    full = int((p / 100.0) * length)
    empty = length - full
    bar = "█" * full + "░" * empty
    
    return f"{bar} {p}%"
