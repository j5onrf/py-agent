def flatten_list(nested):
    """Flatten a list of lists into a single list."""
    return [item for sublist in nested for item in sublist]


def count_occurrences(lst, item):
    """Count how many times an item appears in a list."""
    return lst.count(item)
