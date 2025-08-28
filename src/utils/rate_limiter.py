"""
Rate limiter for API requests.
"""

import asyncio
import time
from typing import Optional
from collections import deque

from .logger import LoggerMixin


class RateLimiter(LoggerMixin):
    """
    Rate limiter for controlling API request frequency and token usage.
    
    Implements sliding window rate limiting for both requests per minute
    and tokens per minute.
    """
    
    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            tokens_per_minute: Maximum tokens per minute
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        
        # Sliding window for requests
        self.request_times = deque()
        
        # Sliding window for tokens
        self.token_usage = deque()  # (timestamp, tokens)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger.info(
            f"Initialized rate limiter: {requests_per_minute} req/min, "
            f"{tokens_per_minute} tokens/min"
        )
    
    async def acquire(self, estimated_tokens: int = 1) -> None:
        """
        Acquire permission to make a request.
        
        Args:
            estimated_tokens: Estimated number of tokens for this request
        
        This method will block until the request can be made within rate limits.
        """
        async with self._lock:
            current_time = time.time()
            
            # Clean old entries
            self._clean_old_entries(current_time)
            
            # Check if we need to wait
            wait_time = self._calculate_wait_time(current_time, estimated_tokens)
            
            if wait_time > 0:
                self.logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
                current_time = time.time()
                self._clean_old_entries(current_time)
            
            # Record the request
            self.request_times.append(current_time)
            self.token_usage.append((current_time, estimated_tokens))
    
    async def update_usage(self, tokens_used: int) -> None:
        """
        Update actual token usage after a request completes.
        
        Args:
            tokens_used: Actual number of tokens used
        """
        async with self._lock:
            # Update the most recent token usage entry
            if self.token_usage:
                timestamp, estimated = self.token_usage[-1]
                self.token_usage[-1] = (timestamp, tokens_used)
                
                self.logger.debug(
                    f"Updated token usage: estimated={estimated}, actual={tokens_used}"
                )
    
    def _clean_old_entries(self, current_time: float) -> None:
        """
        Remove entries older than 1 minute.
        
        Args:
            current_time: Current timestamp
        """
        cutoff_time = current_time - 60  # 1 minute ago
        
        # Clean request times
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
        
        # Clean token usage
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()
    
    def _calculate_wait_time(self, current_time: float, estimated_tokens: int) -> float:
        """
        Calculate how long to wait before making the request.
        
        Args:
            current_time: Current timestamp
            estimated_tokens: Estimated tokens for the request
        
        Returns:
            Wait time in seconds
        """
        wait_times = []
        
        # Check request rate limit
        if len(self.request_times) >= self.requests_per_minute:
            # Find when the oldest request will be outside the window
            oldest_request = self.request_times[0]
            wait_for_request = oldest_request + 60 - current_time
            if wait_for_request > 0:
                wait_times.append(wait_for_request)
        
        # Check token rate limit
        current_tokens = sum(tokens for _, tokens in self.token_usage)
        if current_tokens + estimated_tokens > self.tokens_per_minute:
            # Find when enough tokens will be available
            tokens_needed = current_tokens + estimated_tokens - self.tokens_per_minute
            
            # Calculate when enough tokens will be freed up
            tokens_freed = 0
            for timestamp, tokens in self.token_usage:
                tokens_freed += tokens
                if tokens_freed >= tokens_needed:
                    wait_for_tokens = timestamp + 60 - current_time
                    if wait_for_tokens > 0:
                        wait_times.append(wait_for_tokens)
                    break
        
        return max(wait_times) if wait_times else 0
    
    def get_current_usage(self) -> dict:
        """
        Get current rate limit usage statistics.
        
        Returns:
            Dictionary with current usage information
        """
        current_time = time.time()
        
        # Count requests in the last minute
        cutoff_time = current_time - 60
        recent_requests = sum(1 for t in self.request_times if t >= cutoff_time)
        
        # Count tokens in the last minute
        recent_tokens = sum(tokens for timestamp, tokens in self.token_usage if timestamp >= cutoff_time)
        
        return {
            'requests_used': recent_requests,
            'requests_limit': self.requests_per_minute,
            'requests_remaining': max(0, self.requests_per_minute - recent_requests),
            'tokens_used': recent_tokens,
            'tokens_limit': self.tokens_per_minute,
            'tokens_remaining': max(0, self.tokens_per_minute - recent_tokens),
            'request_utilization': recent_requests / self.requests_per_minute,
            'token_utilization': recent_tokens / self.tokens_per_minute
        }
    
    async def wait_for_capacity(self, tokens_needed: int = 1) -> float:
        """
        Wait until there's capacity for a request with the specified tokens.
        
        Args:
            tokens_needed: Number of tokens needed
        
        Returns:
            Time waited in seconds
        """
        start_time = time.time()
        
        while True:
            async with self._lock:
                current_time = time.time()
                self._clean_old_entries(current_time)
                
                wait_time = self._calculate_wait_time(current_time, tokens_needed)
                if wait_time <= 0:
                    break
            
            await asyncio.sleep(min(wait_time, 1.0))  # Wait at most 1 second at a time
        
        return time.time() - start_time

