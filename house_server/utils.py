def check_json_object_format(target, inpt):
    if target is None:
        return True

    if type(target) != type(inpt):
        return False

    if type(target) == list:
        assert len(target) == 1
        return all([check_json_object_format(target[0], i) for i in inpt])

    for i in target:
        if i not in inpt:
            return False

        if not check_json_object_format(target[i], inpt[i]):
            return False

    return True
