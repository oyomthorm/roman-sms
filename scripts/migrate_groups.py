import csv
import random
from faker import Faker

# Optional: make the output reproducible
Faker.seed(42)
random.seed(42)

fake = Faker()

GROUPS = [f"Group {i}" for i in range(7, 12)]  # Group 7 ... Group 11
MIN_PER_GROUP = 190
MAX_PER_GROUP = 350
OUTPUT_FILE = "contacts.csv"

# Uganda mobile prefixes (after the leading 0, or after +256)
UG_PREFIXES = ["70", "74", "75", "76", "77", "78", "39", "20"]


def uganda_number() -> str:
    """Return a phone number in one of three valid formats:
       0700123456       (local, 10 digits, leading 0)
       256700123456     (country code, 12 digits)
       +256700123456    (international, 13 chars)
    """
    prefix = random.choice(UG_PREFIXES)
    subscriber = "".join(random.choices("0123456789", k=7))
    national = prefix + subscriber

    fmt = random.choice(("local", "cc", "plus"))
    if fmt == "local":
        return "0" + national
    if fmt == "cc":
        return "256" + national
    return "+256" + national


def canonical(num: str) -> str:
    """Normalize any of the 3 formats to +256XXXXXXXXX for dedup checks."""
    if num.startswith("+"):
        return num
    if num.startswith("256"):
        return "+" + num
    return "+256" + num[1:]   # local form: drop leading 0


used: set[str] = set()


def unique_uganda_number() -> str:
    while True:
        num = uganda_number()
        c = canonical(num)
        if c not in used:
            used.add(c)
            return num


# Decide group sizes up front so we can report totals
group_sizes = {
    g: random.randint(MIN_PER_GROUP, MAX_PER_GROUP) for g in GROUPS
}
total = sum(group_sizes.values())

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Phone", "Name", "Group"])

    for group, size in group_sizes.items():
        for _ in range(size):
            writer.writerow([unique_uganda_number(), fake.name(), group])

# Report
print(f"Wrote {total} rows to {OUTPUT_FILE}")
for g, s in group_sizes.items():
    print(f"  {g}: {s} contacts")