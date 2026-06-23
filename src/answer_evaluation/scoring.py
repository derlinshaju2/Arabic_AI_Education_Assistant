def generate_score(similarity):
    similarity = max(0.0, min(1.0, similarity))

    if similarity >= 0.95:
        return 10
    elif similarity >= 0.85:
        return 9
    elif similarity >= 0.75:
        return 8
    elif similarity >= 0.65:
        return 7
    elif similarity >= 0.55:
        return 6
    elif similarity >= 0.45:
        return 5
    elif similarity >= 0.35:
        return 4
    elif similarity >= 0.25:
        return 3
    elif similarity >= 0.15:
        return 2
    elif similarity > 0:
        return 1
    else:
        return 0
