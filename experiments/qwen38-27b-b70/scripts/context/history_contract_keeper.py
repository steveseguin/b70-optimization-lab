#!/usr/bin/env python3
"""Exploratory C66 launcher: production keeper with the frozen C65 memory suffix.

The shared memory instruction is visible in both main and in-place notes
headers. No main-only hook, request rewrite or budget-accounting change.
"""
import main_history_contract_probe as proposal

ck = proposal.ck


def append_once(original):
    count = original.count(proposal.CONTRACT)
    if count:
        if count == 1 and original.endswith(proposal.CONTRACT):
            return original
        raise ValueError('memory contract is already present in an unexpected position')
    return original + proposal.CONTRACT


def install_contract():
    ck.MEMORY_NOTE = append_once(ck.MEMORY_NOTE)


def main():
    install_contract()
    ck.main()


if __name__ == '__main__':
    main()
