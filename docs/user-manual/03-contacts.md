# 3. Adding contacts

Contacts are the people you send messages to — parents, guardians,
staff, customers, members. Before you can send a message to anyone,
their phone number needs to be in your contact list.

You can add contacts one at a time, or many at once from a
spreadsheet. Both are covered here.

## Where contacts live

Every contact in your organization belongs to **exactly one group**.
A group is a named set of contacts — "Form 1 Parents", "Class 6",
"Staff", "Regular customers". Groups are covered in more detail in
Section 4, but the important thing to know here is: **when you add a
contact, you must pick which group they belong to**.

If you don't already have the group you want, you can create it as
part of adding a contact. Roman SMS will offer to create a new group
if the one you type doesn't exist yet.

## Adding a single contact

1. Open the **Contacts** page in the left menu.
2. Click **Add contact** (top-right of the page).
3. Fill in the form:
   - **Name** — optional. If you leave it blank, the contact is
     identified only by their phone number. Filling it in makes the
     contact easier to find later, and lets you use the name in
     personalized messages.
   - **Phone number** — required. Enter it in Ugandan format:
     `0771234567`, `+256771234567`, or `256771234567` all work and
     become the same number.
   - **Group** — required. Pick an existing group from the dropdown,
     or type a new name to create one.
   - **District** — optional. Useful if you send messages by district
     (see Section 5).
   - **Notes** — optional, for your own reference. Only you and your
     staff see these; they are never sent to the contact.
4. Click **Save**.

You'll be taken back to the contacts list. Your new contact is at
the top.

**If the phone number is already in your organization:** Roman SMS
will refuse the duplicate and show an error. This is deliberate —
sending the same message twice to the same phone wastes credits.
If you want to move an existing contact to a different group,
edit that contact (Section 4) rather than adding a new one.

**If the phone number is on the opt-out list:** Roman SMS will add
the contact but immediately mark them opted out. See "Opt-outs"
later in this section.

## Importing contacts from a spreadsheet

If you have your contacts in Excel, Google Sheets, or another
spreadsheet program, you can add them all at once instead of typing
them one by one.

### Preparing your spreadsheet

Save your spreadsheet as a **CSV file** (comma-separated values).
Most spreadsheet programs have an option to save as CSV under "Save
as" or "Export".

Your CSV must have a column named **`phone`**. It can also have:

- **`name`** — optional. The contact's name.
- **`group`** — optional but strongly recommended. If present, each
  row can specify its own group. If absent, you must pick one group
  for the whole file during import.
- **`district`** — optional. Same idea.
- **`opted_out`** — optional. If a row is marked with `1` or `yes`,
  the contact is added but immediately marked as opted out.

The first row of the CSV must be the column names. Example:

    name,phone,group,district
    Mary Nakato,0771234567,Form 1 Parents,Kampala
    John Ssekandi,0772345678,Form 1 Parents,Wakiso
    Sarah Achieng,0773456789,Form 2 Parents,Kampala

Any column names other than `name`, `phone`, `group`, `district`,
`opted_out` are ignored during import. This means you can keep extra
columns in your spreadsheet (like student names or fee balances) and
import the same file — they won't hurt, they just won't be used here.
(They *will* be used if you send personalized messages later. See
Section 5.)

### Importing the file

1. Open the **Contacts** page.
2. Click **Import** (top-right, next to Add contact).
3. Click **Choose file** and pick your CSV.
4. If your CSV does not have a `group` column, choose a **default
   group** to apply to all imported contacts.
5. Click **Import**.

Roman SMS will process the file, add every valid row, and skip any
row it can't add. **You are taken to a report page** that tells you
exactly what happened.

## The import report

The import report is the most useful page in the contact system. It
tells you:

- **How many contacts were added.**
- **How many were skipped, and why.** Every skipped row is recorded
  with the reason and its row number in your CSV.

The reasons a row might be skipped:

- **Invalid phone number.** The number couldn't be recognized as a
  Ugandan phone number. Check the row — was there a typo?
- **Already opted out.** The number is on the platform's opt-out
  list. Roman SMS respects this even if the contact is new to your
  organization.
- **Duplicate within the file.** The same phone number appears twice
  in your CSV. Only the first occurrence is imported.
- **Duplicate in the system.** This phone number is already in your
  organization's contact list. Roman SMS won't create a second copy.
- **No group.** You didn't specify a group for this row and didn't
  choose a default group.

At the top of the report, tabs let you filter by reason — click
"Invalid phone" to see only the invalid rows, for example.

`[SCREENSHOT: The import report with its filter tabs and row counts]`

**Download the error CSV.** Click the **Download errors** button at
the top of the report to save a CSV of every skipped row. Fix the
problems in your spreadsheet, then re-import only those rows. The
imported contacts are already in the system; you don't need to
re-import them.

The import report is saved forever. Come back to it any time by
clicking **Contacts → Imports** — you'll see a list of every import
your organization has ever done.

## Opt-outs

An **opt-out** is a request from a contact to stop receiving messages
from Roman SMS.

Opt-outs are **platform-wide**: once a phone number opts out, it is
opted out for every organization on Roman SMS, not just yours. This
is a legal requirement in Uganda and we enforce it strictly.

### How people opt out

A contact can opt out three ways:

1. **You mark them opted out manually.** Open the contact (Section
   4), click **Opt out**.
2. **You import them with `opted_out=1`** in your CSV.
3. **They opt out via the public landing page** — a web link you or
   the operator can share with them.

### What happens when someone opts out

- The phone number is added to the platform-wide opt-out list.
- Any future campaign you send will skip that number, even if the
  number is still in your contact list.
- The contact stays in your list — they are not deleted — but they
  are marked opted out and won't receive messages.

You can see a contact's opt-out status on their detail page. There
is no way to reverse an opt-out yourself. If a contact asks to be
re-added (they changed their mind), contact the operator — this is
rare and deliberate, because opt-outs are meant to be honored.

### Why opt-outs matter

Sending to a phone number that has opted out is a violation of the
Uganda Data Protection and Privacy Act and of your agreement with
Roman SMS. If a recipient reports you, your organization can be
suspended. **Never try to work around an opt-out** by adding the
same phone number differently, using a different group, or asking
someone else to add them. If the number is opted out, it stays opted
out. Respect it.

## If your contacts list looks wrong

**"I imported 500 contacts but only 480 were added."** Click
**Contacts → Imports**, open the most recent import, and look at
the report. The 20 skipped rows have reasons. Fix them and re-import
those rows only.

**"A contact I added yesterday isn't showing up."** Check the group
filter at the top of the contacts list. If you have more than one
group, the list may be showing only one group's contacts. Change
the filter to "All".

**"I can't add a contact because it says the phone number is a
duplicate."** The number is already in your organization, probably
in a different group. Find them by searching for the number, open
their detail page, and change their group if needed.

**"I marked a contact opted out by mistake."** Contact the operator
— opt-outs cannot be reversed by you, only by them.

---

*Section 3 of 10. See `04-groups.md` next.*