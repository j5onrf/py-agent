def calculate_average(numbers):
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 2)
