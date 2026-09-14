# Calculate the first 10 Fibonacci numbers and write them as a comma-separated list to fib.txt

def fibonacci(n):
    sequence = []
    a, b = 0, 1
    for _ in range(n):
        sequence.append(a)
        a, b = b, a + b
    return sequence

# Calculate the first 10 Fibonacci numbers
fib_numbers = fibonacci(10)

# Write them as a comma-separated list to fib.txt
with open('fib.txt', 'w') as f:
    f.write(','.join(map(str, fib_numbers)))

print("Fibonacci numbers written to fib.txt:", fib_numbers)