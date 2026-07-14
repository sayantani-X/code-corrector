import math
import sys
import unittest


def calculate_log(n: float, b: float) -> float:
    """
    Calculates the logarithm of n with base b: log_b(n).

    Using the change of base formula:
    log_b(n) = ln(n) / ln(b)

    Args:
        n (float): The number to find the logarithm of (must be > 0).
        b (float): The base of the logarithm (must be > 0 and != 1).

    Returns:
        float: The logarithm of n with base b.

    Raises:
        ValueError: If n <= 0, b <= 0, or b == 1.
    """
    if n <= 0:
        raise ValueError("The number (n) must be greater than 0.")
    if b <= 0:
        raise ValueError("The base (b) must be greater than 0.")
    if math.isclose(b, 1.0):
        raise ValueError("The base (b) cannot be 1.")

    return math.log(n) / math.log(b)


class TestLogarithm(unittest.TestCase):
    def test_standard_cases(self):
        self.assertAlmostEqual(calculate_log(8, 2), 3.0)
        self.assertAlmostEqual(calculate_log(100, 10), 2.0)
        self.assertAlmostEqual(calculate_log(1000, 10), 3.0)
        self.assertAlmostEqual(calculate_log(81, 3), 4.0)
        self.assertAlmostEqual(calculate_log(1, 5), 0.0)

    def test_fractional_bases_and_numbers(self):
        self.assertAlmostEqual(calculate_log(0.25, 2), -2.0)
        self.assertAlmostEqual(calculate_log(4, 0.5), -2.0)
        self.assertAlmostEqual(calculate_log(0.125, 0.5), 3.0)

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
        suite = unittest.TestLoader().loadTestsFromTestCase(TestLogarithm)
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
