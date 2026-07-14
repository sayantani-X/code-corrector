"""
Stock Ticker Price Trend Analyzer.

This module implements a modified run-length compression algorithm for stock ticker price trends.
It analyzes a chronological sequence of stock closing prices and converts them into a condensed
list of trend movements ("U" for Up, "D" for Down, "F" for Flat).
"""


def encode_trends(prices: list[float]) -> list[str]:
    """
    Analyzes a chronological sequence of stock closing prices and converts them into a
    condensed list of trend movements using a modified run-length encoding.

    Trend definitions:
    - "U" (Up): price > prev_price
    - "D" (Down): price < prev_price
    - "F" (Flat): price == prev_price

    If prices has fewer than 2 elements, returns an empty list.

    Args:
        prices (list[float]): Chronological sequence of stock closing prices.

    Returns:
        list[str]: Compressed runs of trends (e.g., ['3U', '1F', '2D']).
    """
    if not prices or len(prices) < 2:
        return []

    # Calculate day-to-day trends
    trends = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            trends.append("U")
        elif diff < 0:
            trends.append("D")
        else:
            trends.append("F")

    # Run-length encoding of trends
    compressed = []
    if not trends:
        return compressed

    current_trend = trends[0]
    count = 1

    for trend in trends[1:]:
        if trend == current_trend:
            count += 1
        else:
            compressed.append(f"{count}{current_trend}")
            current_trend = trend
            count = 1

    # Append the last run
    compressed.append(f"{count}{current_trend}")

    return compressed


def run_tests():
    """Runs comprehensive unit tests to verify the correctness of encode_trends."""
    # Test Case 1: Empty list
    res1 = encode_trends([])
    if res1 != []:
        raise ValueError(f"Expected [], got {res1}")

    # Test Case 2: Single element
    res2 = encode_trends([100.0])
    if res2 != []:
        raise ValueError(f"Expected [], got {res2}")

    # Test Case 3: Simple Up trend
    res3 = encode_trends([100.0, 101.0, 102.0, 103.0])
    if res3 != ["3U"]:
        raise ValueError(f"Expected ['3U'], got {res3}")

    # Test Case 4: Simple Down trend
    res4 = encode_trends([100.0, 99.0, 98.0])
    if res4 != ["2D"]:
        raise ValueError(f"Expected ['2D'], got {res4}")

    # Test Case 5: Simple Flat trend
    res5 = encode_trends([100.0, 100.0, 100.0])
    if res5 != ["2F"]:
        raise ValueError(f"Expected ['2F'], got {res5}")

    # Test Case 6: Mixed trends
    # Prices: [100.0, 105.0, 105.0, 102.0, 101.0, 103.0]
    # Day-to-day trends:
    # 100 -> 105: U
    # 105 -> 105: F
    # 105 -> 102: D
    # 102 -> 101: D
    # 101 -> 103: U
    # Sequence: U, F, D, D, U
    # Compressed: 1U, 1F, 2D, 1U
    prices = [100.0, 105.0, 105.0, 102.0, 101.0, 103.0]
    expected = ["1U", "1F", "2D", "1U"]
    res6 = encode_trends(prices)
    if res6 != expected:
        raise ValueError(f"Expected {expected}, got {res6}")

    print("All tests passed successfully!")


if __name__ == "__main__":
    print("Running stock trend analyzer demonstration...")

    # Example stock prices
    example_prices = [150.0, 152.5, 152.5, 151.0, 150.0, 150.0, 153.0, 155.0]
    # Trends:
    # 150.0 -> 152.5: U
    # 152.5 -> 152.5: F
    # 152.5 -> 151.0: D
    # 151.0 -> 150.0: D
    # 150.0 -> 150.0: F
    # 150.0 -> 153.0: U
    # 153.0 -> 155.0: U
    # Sequence: U, F, D, D, F, U, U
    # Compressed: 1U, 1F, 2D, 1F, 2U

    compressed_trends = encode_trends(example_prices)
    print(f"Prices: {example_prices}")
    print(f"Compressed Trends: {compressed_trends}")

    # Run unit tests
    print("\nRunning unit tests...")
    run_tests()
