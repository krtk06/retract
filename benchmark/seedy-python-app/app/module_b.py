from app.module_a import entry_point_a


def helper_b(value):
    return entry_point_a(value) if value > 10 else value * 2
