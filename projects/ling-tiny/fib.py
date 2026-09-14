# Calculate the first 10 Fibonacci numbers and write them as a comma-separated list to fib.txt

def fibonacci(n):
    fibs = []
    a, b = 0, 1
    for _ in range(n):
        fibs.append(a)
        a, b = b, a + b
    return fibs

# Get the first 10 Fibonacci numbers
numbers = fibonacci(10)

# Write them as a comma-separated list to fib.txt
with open('fib.txt', 'w') as f:
    f.write(','.join(map(str, numbers)))

print(f"First 10 Fibonacci numbers: {numbers}")
print(f"Written to fib.txt: {','.join(map(str, numbers))}")