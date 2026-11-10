# 4. Organizing contacts into groups

A **group** is a named set of contacts. Every contact in your
organization belongs to exactly one group. Groups are how you target
your messages — you send to "Form 1 Parents" instead of "everyone in
the school", or to "Regular customers" instead of "every number we
have".

You can have as many groups as you want. Common examples:

- **School:** "Form 1 Parents", "Form 2 Parents", "Class 6", "Staff",
  "PTA Members", "Old Students".
- **Business:** "VIP Customers", "Wholesale", "Retail", "Staff".
- **Any organization:** "Everyone" (put all your contacts in one
  group if you don't need finer control).

## Creating a group

1. Open the **Groups** page in the left menu.
2. Click **New group** (top-right).
3. Fill in:
   - **Name** — what the group is for. Short and clear is best.
   - **Description** — optional. A sentence about what the group
     means, for your own reference.
4. Click **Save**.

The group appears in the list immediately with zero contacts. To add
contacts to it, see below.

**If your organization uses departments** (school setups with a
bursar, DOS, dean, and HT), the group belongs to *your* department
unless you are the school administrator. Administrators create
groups that everyone can see. Bursars create groups that only
bursars and administrators can see. You can't change this at group
creation — it's set automatically from your account.

`[SCREENSHOT: The Groups list showing a few groups with contact counts]`

## Adding contacts to a group

There are three ways:

### Add new contacts straight into a group

When you add a contact (Section 3), pick the group in the dropdown
on the contact form. The contact goes straight into that group.

### Move existing contacts into a group

1. Open the contact (from the Contacts page — click the contact's
   name or email).
2. Click **Edit**.
3. Change the **Group** dropdown to the new group.
4. Click **Save**.

The contact moves from their old group to the new one. They are
never in two groups at once.

### Move many contacts at once

Open the group you want to move contacts *out of*, or search for
contacts by name/phone on the Contacts page. Roman SMS doesn't
currently offer a "move all from group A to group B" bulk button —
for large reorganizations, contact the operator for help. Small
moves (up to a few dozen contacts) are fastest through the per
contact edit form.

## Seeing who's in a group

Click any group on the Groups page to see:

- **The list of contacts** in that group.
- **The total count** at the top.
- **A search box** to find a specific contact within the group.
- **An import button** to add more contacts to this group from a
  CSV (same as Section 3, but pre-selected to this group).

`[SCREENSHOT: A group detail page showing contacts and search]`

## Renaming a group

1. Open the Groups page.
2. Click the group's name.
3. Click **Edit** (top-right).
4. Change the name or description.
5. Click **Save**.

The contacts inside the group are unaffected. Anything that
references the group (for instance, a scheduled campaign targeted at
this group) will see the new name going forward.

## Deleting a group

**Read this before you delete a group.**

Deleting a group is a permanent action. There is no undo.

When you delete a group:

- **The group itself is removed.**
- **The contacts inside it are not deleted** — they stay in your
  contact list — **but they become ungrouped.** An ungrouped contact
  cannot receive messages until you assign them to a group.

In practice, this means: if you're reorganizing, move contacts to
the new group first, then delete the old one. Otherwise you'll end
up with contacts that can't be messaged until they're re-grouped.

To delete:

1. Open the group.
2. Click **Delete** (top-right, or in the menu next to Edit).
3. Confirm.

**If a scheduled campaign uses this group** (a message scheduled to
send to this group at a future date), Roman SMS won't warn you — it
will delete the group, and the schedule will be orphaned. The
schedule may still fire using a snapshot of the recipients that were
captured when the schedule was created, but it won't be able to pick
up new contacts added later, and the schedule will show a missing
group if you open it.

**Cancel any scheduled campaigns that target a group before
deleting the group.** This is the safest habit. To check: open
**Campaigns → Scheduled** and look at what each scheduled campaign
targets.

`[SCREENSHOT: The delete group confirmation dialog]`

## Groups and departments (school administrators)

If your school uses departments, the Groups page shows only:

- Groups **you** created (belonging to your department, or shared if
  you are the school administrator).
- Groups created by **other school administrators** (shared).
- **Not** groups created by bursars or deans if you are not one.

This is the department isolation system at work. To see all groups,
you need to be the school administrator. If you need to see a
different department's groups for a specific reason, ask that
department's staff member to share the contacts with you, or ask the
school administrator to move contacts between groups.

## Common group setups

A few patterns that work well. Copy whichever fits your organization
and adjust.

### Small school (fewer than 200 contacts)

- One group per class: "Form 1", "Form 2", "Form 3", "Form 4".
- One group for staff: "Staff".
- One group for parents who aren't class-specific: "All Parents".

### Large school

- One group per class: "Form 1A", "Form 1B", "Form 2A", ...
- One group per stream or house, if you use them.
- One group per role: "Parents", "Guardians", "Staff", "Alumni".
- District groups only if you actually send by district — otherwise
  districts add noise.

### Business

- One group per customer tier: "VIP", "Wholesale", "Retail".
- One group for staff.
- One group for past customers you might want to re-engage.

### Just starting out

- One group called "Everyone" for all your contacts. Split into
  finer groups later when you actually need to send differently to
  different people.

## If your groups list looks wrong

**"My groups list is shorter than I expected."** If you are not a
school administrator, you only see your own department's groups plus
shared ones. Other departments' groups are hidden. Ask your school
administrator if you need to see them.

**"A contact is in the wrong group."** Open the contact, click Edit,
change the Group dropdown, save. Contacts are in one group at a
time — the move is immediate.

**"I deleted a group by mistake."** The group is gone. The contacts
that were in it are now ungrouped. You'll need to recreate the group
and move contacts into it individually. There is no undo. This is
why deleting groups requires confirmation — take that confirmation
seriously.

**"The group shows 'null contacts' or an empty count."** This can
happen briefly after a page load if the count hasn't refreshed yet.
Wait a moment and reload. If it stays empty, click the group to see
the actual contact list — the count and the list read from the same
data, so if the list is populated, the count will catch up.

---

*Section 4 of 10. See `05-sending-a-message.md` next.*