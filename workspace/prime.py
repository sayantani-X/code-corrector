def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def get_first_n_primes(n: int) -> list[int]:
    primes = []
    candidate = 2
    while len(primes) < n:
        if is_prime(candidate):
            primes.append(candidate)
        candidate += 1
    return primes

if __name__ == "__main__":
    first_15_primes = get_first_n_primes(15)
    print("The first 15 prime numbers are:")
    print(first_15_primes)
