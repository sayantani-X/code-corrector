import sys
import unittest


def calculate_log(n: float, b: float, precision: int = 12) -> float:
    """
    Calculates the logarithm of n with base b: log_b(n) without using the math library.

    Args:
        n (float): The number to find the logarithm of (must be > 0).
        b (float): The base of the logarithm (must be > 1).
        precision (int): Number of decimal places of precision for the fractional part.

    Returns:
        float: The logarithm of n with base b.

    Raises:
        ValueError: If n <= 0 or b <= 1.
    """
    if n <= 0:
        raise ValueError("The target number (n) must be greater than 0.")
    if b <= 1:
        raise ValueError("The base (b) must be greater than 1.")

    # Handle the case where n is 1: log_b(1) is always 0
    if abs(n - 1.0) < 1e-15:
        return 0.0

    # If n < 1, we can use the identity: log_b(n) = -log_b(1/n)
    if n < 1.0:
        return -calculate_log(1.0 / n, b, precision)

    # Now we have b > 1 and n > 1.
    # 1. Find the integer part (floor) of log_b(n)
    integer_part = 0
    temp = n
    while temp >= b:
        temp /= b
        integer_part += 1

    # 2. Find the fractional part using a high-precision bisection search.
    # Since temp = n / b^(integer_part), we have 1 <= temp < b.
    # We want to find x = log_b(temp) such that 0 <= x < 1.
    # This is equivalent to finding x such that b^x = temp.
    # We can use bisection search on the interval [0, 1].
    low = 0.0
    high = 1.0
    
    # Run bisection search for a fixed number of iterations to guarantee precision.
    # Each iteration halves the interval. 50 iterations give a precision of 2^-50 ≈ 8.88e-16.
    for _ in range(60):
        mid = (low + high) / 2.0
        # Compute b^mid using the identity b^mid = b^(integer_part_of_mid + fractional_part_of_mid)
        # Since mid is in [0, 1], we can compute b^mid using a binary exponentiation-like method
        # for fractional powers, or we can compute it directly by approximating the power.
        # Alternatively, we can use the digit-by-digit extraction method which is already highly precise,
        # or we can implement a robust fractional power function.
        # Let's stick to the digit-by-digit extraction method as it is mathematically equivalent to
        # a binary bisection search on the exponent and is extremely efficient and accurate.
        # Let's refine the digit-by-digit extraction to ensure maximum precision.
        pass

    # Refined digit-by-digit extraction (binary search on fractional bits):
    fractional_part = 0.0
    divisor = 2.0
    # 52 iterations correspond to the 52 bits of mantissa in a double-precision float.
    for _ in range(52):
        temp = temp * temp
        if temp >= b:
            fractional_part += 1.0 / divisor
            temp /= b
        divisor *= 2.0

    return integer_part + fractional_part


class TestManualLog(unittest.TestCase):
    def test_standard_cases(self):
        self.assertAlmostEqual(calculate_log(8, 2), 3.0, places=7)
        self.assertAlmostEqual(calculate_log(100, 10), 2.0, places=7)
        self.assertAlmostEqual(calculate_log(1000, 10), 3.0, places=7)
        self.assertAlmostEqual(calculate_log(81, 3), 4.0, places=7)
        self.assertAlmostEqual(calculate_log(1, 5), 0.0, places=7)

    def test_fractional_numbers(self):
        self.assertAlmostEqual(calculate_log(0.25, 2), -2.0, places=7)
        self.assertAlmostEqual(calculate_log(0.125, 2), -3.0, places=7)

    def test_fractional_results(self):
        # log_2(10) is approx 3.321928094887
        self.assertAlmostEqual(calculate_log(10, 2), 3.321928094887, places=5)
        # log_10(2) is approx 0.30102999566
        self.assertAlmostEqual(calculate_log(2, 10), 0.30102999566, places=5)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            calculate_log(-5, 2)
        with self.assertRaises(ValueError):
            calculate_log(0, 2)
        with self.assertRaises(ValueError):
            calculate_log(8, -2)
        with self.assertRaises(ValueError):
            calculate_log(8, 0)
        with self.assertRaises(ValueError):
            calculate_log(8, 1)
        with self.assertRaises(ValueError):
            calculate_log(8, 0.5)


if __name__ == "__main__":
    # If arguments are provided, run as a CLI tool
    if len(sys.argv) > 2:
        try:
            n_val = float(sys.argv[1])
            b_val = float(sys.argv[2])
            result = calculate_log(n_val, b_val)
            print(f"log_{b_val}({n_val}) = {result}")
        except ValueError as e:
            print(f"Error: {e}")
    else:
        # Otherwise, run the test suite and then prompt for interactive input
        print("Running test suite...")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestManualLog)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        if result.wasSuccessful():
            print("\nAll tests passed successfully!")
            print("\n--- Interactive Mode ---")
            try:
                n_input = input("Enter the number (n): ")
                b_input = input("Enter the base (b): ")
                if n_input.strip() and b_input.strip():
                    n_val = float(n_input)
                    b_val = float(b_input)
                    ans = calculate_log(n_val, b_val)
                    print(f"log_{b_val}({n_val}) = {ans}")
            except ValueError as e:
                print(f"Error: {e}")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
        else:
            sys.exit(1)
