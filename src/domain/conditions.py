"""Small, fail-closed condition vocabulary. Unknown never implies reachable."""


def validate_condition(value: dict) -> None:
    if not isinstance(value, dict) or 'op' not in value:
        raise ValueError('Condition must be an object with op')
    op = value['op']
    if op in {'and', 'or'}:
        if set(value) != {'op', 'args'} or not isinstance(value['args'], list) or not value['args']:
            raise ValueError('and/or require nonempty args')
        for arg in value['args']:
            validate_condition(arg)
    elif op == 'unknown':
        if set(value) != {'op', 'reason'} or not isinstance(value['reason'], str) or not value['reason']:
            raise ValueError('Unknown conditions require a reason')
    elif op == 'level_at_least':
        if set(value) != {'op', 'value'} or type(value['value']) is not int or not 1 <= value['value'] <= 100:
            raise ValueError('Invalid level condition')
    elif op in {'has_pokemon', 'has_item', 'at_location', 'milestone', 'encounter_condition', 'encounter_pokemon'}:
        if set(value) != {'op', 'value'} or not isinstance(value['value'], str) or not value['value']:
            raise ValueError('Condition requires a nonempty identifier')
    elif op == 'always':
        if set(value) != {'op'}:
            raise ValueError('always takes no arguments')
    else:
        raise ValueError(f'Unsupported condition: {op}')


def evaluate_condition(value: dict, context: dict) -> bool | None:
    """Three-valued evaluation. Absent context means unknown, not false."""
    validate_condition(value)
    op = value['op']
    if op == 'unknown':
        return None
    if op == 'always':
        return True
    if op in {'and', 'or'}:
        results = [evaluate_condition(arg, context) for arg in value['args']]
        decisive = False if op == 'and' else True
        if decisive in results:
            return decisive
        return None if None in results else not decisive
    if op == 'level_at_least':
        return None if 'level' not in context else context['level'] >= value['value']
    if op not in context:
        return None
    return value['value'] in context[op]
