from app.module_b import helper_b


def entry_point_a(value):
    return helper_b(value) + 1
