"""Race-safe auto-numbering helpers.

Auto-generated identifiers (``EST-YYYY-NNN``, ``PRY-YYYY-NNN``, ``SO-YYYY-NNN``)
are derived from the current maximum, which **races** under concurrent creation:
two requests read the same max and generate the same number. Because the
underlying columns are ``unique``, the loser hits an ``IntegrityError`` instead
of silently duplicating -- but the create still fails for the user.

These helpers fix both problems:

* :func:`next_numbered_code` derives the next value from the numeric suffix of
  the current maximum (robust to deleted rows, unlike a ``count()``-based scheme
  which can collide after a delete).
* :func:`create_with_retry` retries the create with a freshly-computed number on
  ``IntegrityError``, so a concurrent collision resolves to the next free value
  instead of erroring.

The retry is the actual concurrency guard; the column ``unique`` constraint is
what turns a race into a catchable ``IntegrityError``. ``select_for_update`` is
intentionally avoided so the behaviour is identical on SQLite (dev) and
PostgreSQL (prod).
"""

from django.db import IntegrityError, transaction


def next_numbered_code(model, field, prefix, *, width):
    """Return the next ``{prefix}{NNN}`` code for ``model.field``.

    Uses the numeric suffix of the lexically-greatest existing value carrying
    this prefix. Zero-padded suffixes sort identically lexically and numerically,
    so the lexical max is the numeric max -- and it is robust to deleted rows
    (unlike ``count() + 1``, which re-issues a freed number and collides).

    :param model: the Django model class.
    :param field: name of the unique char field holding the code.
    :param prefix: literal prefix, e.g. ``"EST-2026-"``.
    :param width: zero-pad width of the numeric suffix (e.g. ``3`` -> ``007``).
    """
    last = (
        model.objects.filter(**{f"{field}__startswith": prefix})
        .order_by(f"-{field}")
        .values_list(field, flat=True)
        .first()
    )
    next_seq = 1
    if last:
        suffix = last[len(prefix):]
        if suffix.isdigit():
            next_seq = int(suffix) + 1
    return f"{prefix}{next_seq:0{width}d}"


def create_with_retry(operation, *, max_retries=5):
    """Run ``operation()`` in an atomic block, retrying on ``IntegrityError``.

    ``operation`` must (re)compute its unique auto-number on every call -- e.g.
    via :func:`next_numbered_code` -- so a retry after a concurrent collision
    picks the next free value. Each attempt runs inside ``transaction.atomic``,
    which uses a savepoint when already inside an outer transaction, so this is
    safe to call from a method that is itself ``@transaction.atomic``.

    :raises IntegrityError: if every attempt collides (re-raises the last one).
    """
    last_exc = None
    for _ in range(max_retries):
        try:
            with transaction.atomic():
                return operation()
        except IntegrityError as exc:
            last_exc = exc
    raise last_exc
