def fibonacci(n):
    seq = []
    a, b = 0, 1
    while len(seq) < n:
        seq.append(a)
        a, b = b, a + b
    return seq

if __name__ == '__main__':
    result = fibonacci(10)
    print(result)