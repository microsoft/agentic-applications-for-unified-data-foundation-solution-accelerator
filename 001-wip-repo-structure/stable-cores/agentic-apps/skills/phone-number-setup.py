#!/usr/bin/env python3
"""Acquire an Azure Communication Services phone number after cost approval."""

import argparse
import sys

from azure.communication.phonenumbers import (
    PhoneNumberAssignmentType,
    PhoneNumberCapabilities,
    PhoneNumberCapabilityType,
    PhoneNumbersClient,
    PhoneNumberType,
)
from azure.identity import DefaultAzureCredential

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Acquire an Azure Communication Services phone number"
    )
    parser.add_argument("--endpoint", required=True, help="Communication Services endpoint")
    parser.add_argument("--country", default="US", help="ISO 3166-1 alpha-2 country code")
    parser.add_argument(
        "--type",
        dest="number_type",
        choices=["toll-free", "geographic"],
        default="toll-free",
        help="Phone number type",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Purchase without an interactive confirmation",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    """Search for and purchase one phone number."""
    client = PhoneNumbersClient(args.endpoint, DefaultAzureCredential())
    number_type = (
        PhoneNumberType.TOLL_FREE
        if args.number_type == "toll-free"
        else PhoneNumberType.GEOGRAPHIC
    )
    capabilities = PhoneNumberCapabilities(
        calling=PhoneNumberCapabilityType.INBOUND_OUTBOUND,
        sms=PhoneNumberCapabilityType.NONE,
    )
    search = client.begin_search_available_phone_numbers(
        country_code=args.country.upper(),
        phone_number_type=number_type,
        assignment_type=PhoneNumberAssignmentType.APPLICATION,
        capabilities=capabilities,
        quantity=1,
    ).result()

    if not search.phone_numbers:
        print("No matching phone numbers are available.", file=sys.stderr)
        return EXIT_FAILURE

    phone_number = search.phone_numbers[0]
    print(f"Phone number: {phone_number}")
    if search.cost:
        print(f"Recurring cost: {search.cost.amount} {search.cost.currency_code}")

    if not args.auto_approve:
        confirmation = input("Purchase this number? [y/N] ").strip().lower()
        if confirmation not in {"y", "yes"}:
            print("Purchase cancelled.")
            return EXIT_SUCCESS

    client.begin_purchase_phone_numbers(search.search_id).result()
    print(f"Purchased {phone_number}.")
    return EXIT_SUCCESS


def main() -> int:
    """Run the phone-number setup command."""
    return run(create_parser().parse_args())


if __name__ == "__main__":
    sys.exit(main())
