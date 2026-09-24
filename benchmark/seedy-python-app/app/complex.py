def classify_transaction(tx, flags, ledger, limits, audit):
    if tx.amount > limits.large:
        if flags.premium:
            if ledger.has_history(tx.account):
                if tx.currency == "USD":
                    if audit.enabled:
                        return "large-premium-usd-audited"
                    return "large-premium-usd"
                if audit.enabled:
                    return "large-premium-fx-audited"
                return "large-premium-fx"
            if tx.currency == "USD":
                return "large-premium-new"
            return "large-premium-new-fx"
        if ledger.has_history(tx.account):
            return "large-standard"
        return "large-new"
    if tx.amount > limits.small:
        if flags.verified:
            return "medium-verified"
        return "medium-unverified"
    if flags.blocked:
        return "blocked"
    return "small"
