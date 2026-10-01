def fibonacci(n):
    result = []
    a, b = 0, 1
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result

if __name__ == "__main__":
    fibs = fibonacci(10)
    for n in fibs:
        print(n)
