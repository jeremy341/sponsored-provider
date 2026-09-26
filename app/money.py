from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext


NANO_USD_PER_TOKEN_RATE_UNIT = Decimal("1000")


def rate_cost_nano_usd(
    uncached_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    input_rate: Decimal,
    output_rate: Decimal,
    cached_rate: Decimal | None = None,
) -> int:
    counts = (uncached_input_tokens, cached_input_tokens, output_tokens)
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in counts):
        raise ValueError("token counts must be non-negative integers")

    def as_rate(value: Decimal) -> Decimal:
        if isinstance(value, bool):
            raise ValueError("rates must be finite non-negative decimals")
        try:
            rate = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("rates must be finite non-negative decimals") from None
        if not rate.is_finite() or rate < 0:
            raise ValueError("rates must be finite non-negative decimals")
        return rate

    input_price = as_rate(input_rate)
    output_price = as_rate(output_rate)
    cache_price = as_rate(cached_rate) if cached_rate is not None else input_price
    rate_inputs = (
        (uncached_input_tokens, input_price),
        (cached_input_tokens, cache_price),
        (output_tokens, output_price),
    )
    nonzero_inputs = [(count, rate) for count, rate in rate_inputs if count and rate]
    if nonzero_inputs:
        max_adjusted = max(rate.adjusted() + len(str(count)) for count, rate in nonzero_inputs)
        min_exponent = min(rate.as_tuple().exponent for _, rate in nonzero_inputs)
        precision = max(28, max_adjusted - min_exponent + 4)
    else:
        precision = 28
    with localcontext() as context:
        context.prec = precision
        terms = tuple(Decimal(count) * rate for count, rate in rate_inputs)
        total = sum(terms, Decimal(0)) * NANO_USD_PER_TOKEN_RATE_UNIT
        return int(total.to_integral_value(rounding=ROUND_CEILING))
