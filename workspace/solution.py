import sys
import unittest


def climb_stairs(n: int) -> int:
    """
    Computes the number of distinct ways to climb a staircase of n steps,
    where each time you can either climb 1 or 2 steps.

    This is a variation of the Fibonacci sequence:
    ways(n) = ways(n-1) + ways(n-2)
    with base cases:
    ways(1) = 1
    ways(2) = 2

    Time Complexity: O(n)
    Space Complexity: O(1)
    """
    if n <= 0:
        return 0
    if n == 1:
        return 1
    if n == 2:
        return 2

    first = 1
    second = 2
    for _ in range(3, n + 1):
        third = first + second
        first = second
        second = third
    return second


class TestClimbStairs(unittest.TestCase):
    def test_edge_cases(self):
        self.assertEqual(climb_stairs(0), 0)
        self.assertEqual(climb_stairs(-5), 0)

    def test_base_cases(self):
        self.assertEqual(climb_stairs(1), 1)
        self.assertEqual(climb_stairs(2), 2)

    def test_small_values(self):
        # n = 3: [1,1,1], [1,2], [2,1] -> 3 ways
        self.assertEqual(climb_stairs(3), 3)
        # n = 4: [1,1,1,1], [1,1,2], [1,2,1], [2,1,1], [2,2] -> 5 ways
        self.assertEqual(climb_stairs(4), 5)
        # n = 5: 8 ways
        self.assertEqual(climb_stairs(5), 8)

    def test_large_value(self):
        # n = 10 -> 89 ways
        self.assertEqual(climb_stairs(10), 89)


if __name__ == "__main__":
    # If arguments are provided, run as a CLI tool
    if len(sys.argv) > 1:
        try:
            val = int(sys.argv[1])
            print(f"Number of distinct ways to climb {val} steps: {climb_stairs(val)}")
        except ValueError:
            print("Please provide a valid integer for the number of steps.")
    else:
        # Otherwise, run the test suite and then prompt for interactive input
        print("Running test suite...")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestClimbStairs)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        if result.wasSuccessful():
            print("\nAll tests passed successfully!")
            print("\n--- Interactive Mode ---")
            try:
                prompt = "Enter the number of steps (n) to calculate (or press Enter to exit): "
                user_input = input(prompt)
                if user_input.strip():
                    n_steps = int(user_input)
                    ans = climb_stairs(n_steps)
                    print(f"Number of distinct ways to climb {n_steps} steps: {ans}")
            except ValueError:
                print("Invalid input. Please enter an integer.")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
        else:
            sys.exit(1)
