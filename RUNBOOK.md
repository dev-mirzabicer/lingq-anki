# LingQ-Anki Sync Add-on Runbook

Manual QA instructions and safety checklist for the LingQ-Anki sync add-on.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Getting Your LingQ API Token](#2-getting-your-lingq-api-token)
3. [Creating a Profile](#3-creating-a-profile)
4. [Running Dry-Run](#4-running-dry-run)
5. [Applying Changes](#5-applying-changes)
6. [Understanding Conflicts](#6-understanding-conflicts)
7. [Token Rotation](#7-token-rotation)
8. [Safety Checklist](#8-safety-checklist)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Installation

### Prerequisites

- Anki 2.1.50 or later
- Active LingQ account with API access
- Python 3.9+ (bundled with Anki)

### Installation Steps

1. **Download the add-on**
   - Option A: Install from AnkiWeb (add-on code: TBD)
   - Option B: Manual installation from source

2. **Manual installation from source**
   - Locate your Anki add-ons folder:
     - **Windows**: `%APPDATA%\Anki2\addons21\`
     - **macOS**: `~/Library/Application Support/Anki2/addons21/`
     - **Linux**: `~/.local/share/Anki2/addons21/`
   - Create a new folder named `lingq_sync` (or any unique name)
   - Copy all `.py` files from this repository into that folder
   - Restart Anki

3. **Verify installation**
   - Open Anki
   - Navigate to **Tools** menu
   - You should see **"LingQ Sync..."** option
   - Clicking it opens the sync dialog (placeholder UI initially)

---

## 2. Getting Your LingQ API Token

Your API token authenticates requests to LingQ. **Never share this token.**

### Steps to Obtain Token

1. Log in to [LingQ.com](https://www.lingq.com)
2. Navigate to **Settings** → **Account** → **API**
   - Direct URL: `https://www.lingq.com/en/accounts/apikey/`
3. Your API key is displayed on this page
4. Copy the token (it looks like a long alphanumeric string)

### Storing the Token Securely

The add-on uses an `api_token_ref` field in profiles. This is a **reference name**, not the actual token.

**Recommended approaches:**

- **Environment variable**: Set `LINGQ_API_TOKEN` in your system environment
- **Anki secrets file**: Store in a separate JSON file outside the add-on config
- **Keychain/credential manager**: Use your OS's secure storage

**Never store the raw token in the add-on's `config.json`.**

---

## 3. Creating a Profile

A profile defines how LingQ and Anki data map to each other.

### Profile Configuration Fields

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Unique profile identifier | `"swedish-vocab"` |
| `lingq_language` | LingQ language code | `"sv"` (Swedish) |
| `meaning_locale` | Translation language | `"en"` (English) |
| `api_token_ref` | Reference to your API token | `"LINGQ_API_TOKEN"` |
| `enable_scheduling_writes` | Sync progress/scheduling | `false` (default) |

### Field Mappings

#### LingQ → Anki (`lingq_to_anki`)

Maps LingQ card fields to Anki note fields:

```json
{
  "note_type": "Basic",
  "field_mapping": {
    "term": "Front",
    "hints": "Back"
  },
  "identity_fields": {
    "pk_field": "LingQ_PK",
    "canonical_term_field": "LingQ_TermCanonical"
  }
}
```

- `note_type`: The Anki note type to create/update
- `field_mapping`: LingQ field → Anki field name
- `identity_fields`: Fields used to track LingQ identity in Anki

#### Anki → LingQ (`anki_to_lingq`)

Maps Anki note fields back to LingQ:

```json
{
  "term_field": "Front",
  "translation_fields": ["Back"],
  "primary_card_template": null
}
```

- `term_field`: Anki field containing the vocabulary term
- `translation_fields`: Anki fields containing translations/hints
- `primary_card_template`: Optional; specifies which card template to use

### Step-by-Step Profile Creation

1. **Open Anki** and go to **Tools** → **Add-ons**
2. Select the LingQ Sync add-on and click **Config**
3. You'll see a JSON editor with the configuration structure
4. Add your profile to the `profiles` array:

```json
{
  "config_version": 1,
  "profiles": [
    {
      "name": "my-swedish",
      "lingq_language": "sv",
      "meaning_locale": "en",
      "api_token_ref": "LINGQ_API_TOKEN",
      "enable_scheduling_writes": false,
      "lingq_to_anki": {
        "note_type": "Basic",
        "field_mapping": {
          "term": "Front",
          "hints": "Back"
        },
        "identity_fields": {
          "pk_field": "LingQ_PK",
          "canonical_term_field": "LingQ_TermCanonical"
        }
      },
      "anki_to_lingq": {
        "term_field": "Front",
        "translation_fields": ["Back"],
        "primary_card_template": null
      }
    }
  ]
}
```

5. Click **Save** and restart Anki

### Verifying Your Profile

After saving:
- Open **Tools** → **LingQ Sync...**
- The dialog should load without errors
- Your profile should appear in the profile selector (when UI is complete)

---

## 4. Running Dry-Run

**Always run a dry-run before applying changes.** This previews what will happen without modifying any data.

### What Dry-Run Does

1. Fetches all LingQ cards for the configured language
2. Scans Anki notes matching the configured note type
3. Computes a **sync plan** showing proposed operations
4. Displays counts and details without executing changes

### Interpreting Dry-Run Output

The sync plan shows operation counts by type:

| Operation | Meaning |
|-----------|---------|
| `create_anki` | New Anki notes to create from LingQ cards |
| `create_lingq` | New LingQ cards to create from Anki notes |
| `link` | Existing Anki notes to link with LingQ cards |
| `update_hints` | LingQ hints to update |
| `update_status` | LingQ status changes |
| `reschedule_anki` | Anki cards to reschedule (if scheduling enabled) |
| `conflict` | Ambiguous matches requiring resolution |
| `skip` | Items skipped due to policy (e.g., polysemy) |

### Example Dry-Run Output

```
Sync Plan Summary:
  create_anki: 45
  link: 230
  update_hints: 12
  conflict: 3
  skip: 8

Conflicts (3):
  - "bank" → 2 LingQ matches (polysemy)
  - "run" → 3 LingQ matches (polysemy)
  - "set" → 2 LingQ matches (different contexts)

Skipped (8):
  - 8 cards with multiple hints in meaning locale (polysemy)
```

### What to Look For

1. **Reasonable counts**: Do the numbers make sense for your vocabulary size?
2. **Conflicts**: Review each conflict to understand why matching failed
3. **Skips**: Polysemy skips are expected and safe
4. **No unexpected operations**: Large `create_*` counts may indicate misconfiguration

---

## 5. Applying Changes

Only apply changes after reviewing the dry-run output.

### When It's Safe to Apply

- Dry-run counts look reasonable
- You understand all conflicts
- You've backed up your Anki collection
- You're not in an active study session

### What Happens During Apply

1. **Link operations** execute first (safest)
2. **Create operations** add new items
3. **Update operations** modify existing data
4. **Conflicts and skips** are logged but not executed

### Checkpoint System

The add-on uses checkpoints for crash recovery:

- Progress is saved after each operation
- If interrupted, resume from the last checkpoint
- Checkpoint files: `.lingq_sync_checkpoint_{profile_name}.json`

### Post-Apply Verification

After applying:

1. **Check Anki**: Browse notes to verify new cards look correct
2. **Check LingQ**: Verify hints and status updates applied
3. **Review logs**: Check for any errors in the sync log

---

## 6. Understanding Conflicts

Conflicts occur when the add-on cannot determine a unique match.

### Types of Conflicts

#### Ambiguous Match (Multiple Candidates)

**Cause**: Multiple LingQ cards match the same Anki term.

**Example**: The word "bank" exists as:
- "bank" (financial institution)
- "bank" (river bank)

**Resolution**: The add-on skips these to avoid incorrect linking. You can:
- Manually link in LingQ by adding a unique hint
- Add context to your Anki card's translation field

#### Polysemy Skip

**Cause**: A LingQ card has multiple hints in your meaning locale.

**Example**: "run" with hints:
- "to move quickly"
- "to operate (a machine)"
- "a jog"

**Why skipped**: The add-on cannot determine which meaning your Anki card represents.

**Resolution**: This is intentional safety behavior. Options:
- Accept the skip (recommended for most cases)
- Consolidate hints in LingQ to a single primary meaning
- Create separate Anki cards for each meaning

### Conflict Details in Logs

Conflicts include diagnostic information:

```
conflict: term="bank"
  candidates: [pk=12345, pk=12346]
  reason: "ambiguous_match"
  details: {
    "candidate_count": 2,
    "hints_locale": "en"
  }
```

---

## 7. Token Rotation

API tokens may expire or need rotation for security.

### When to Rotate

- Token stops working (401 errors)
- Security best practice (every 90 days)
- Suspected token compromise

### Rotation Steps

1. **Generate new token** on LingQ:
   - Go to `https://www.lingq.com/en/accounts/apikey/`
   - Regenerate or create a new API key

2. **Update your token storage**:
   - If using environment variable: Update `LINGQ_API_TOKEN`
   - If using secrets file: Update the token value
   - If using keychain: Update the stored credential

3. **Verify the new token**:
   - Open Anki
   - Run a dry-run sync
   - Confirm no authentication errors

4. **Revoke old token** (if LingQ supports this):
   - Check LingQ settings for token management

### Token Troubleshooting

If you see `LingQ API HTTP 401`:
- Token is invalid or expired
- Token was not loaded correctly
- Check your `api_token_ref` matches your storage method

---

## 8. Safety Checklist

**Complete this checklist before every sync run.**

### Pre-Run Verification

- [ ] **Backed up Anki collection**
  - File → Export → Anki Collection Package (.colpkg)
  - Store backup in a safe location

- [ ] **Running on test profile first** (for new configurations)
  - Create a test Anki profile with sample data
  - Verify sync behavior before running on main collection

- [ ] **Reviewed dry-run counts**
  - Run dry-run and examine all operation counts
  - Verify numbers are reasonable for your vocabulary size

- [ ] **Understood conflict resolutions**
  - Review all conflicts in dry-run output
  - Understand why each conflict occurred
  - Accept that conflicts will be skipped

- [ ] **Not running during active study session**
  - Close any review sessions
  - Ensure no other Anki operations are in progress
  - Avoid syncing while AnkiWeb sync is running

### Additional Safety Notes

1. **No deletes**: This add-on never deletes cards on either side
2. **Progress sync is opt-in**: `enable_scheduling_writes` defaults to `false`
3. **Polysemy protection**: Cards with multiple meanings are automatically skipped
4. **Idempotent operations**: Running sync multiple times is safe

### Emergency Recovery

If something goes wrong:

1. **Stop the sync** immediately (close dialog)
2. **Restore from backup**: File → Import → select your .colpkg backup
3. **Check checkpoint file**: Delete `.lingq_sync_checkpoint_*` to reset state
4. **Review logs**: Check Anki's debug console for error details

---

## 9. Troubleshooting

### Common Issues and Solutions

#### "LingQ API HTTP 401"

**Cause**: Invalid or expired API token.

**Solution**:
1. Verify your token at `https://www.lingq.com/en/accounts/apikey/`
2. Check that `api_token_ref` correctly references your token
3. Regenerate token if necessary (see [Token Rotation](#7-token-rotation))

#### "LingQ API HTTP 429"

**Cause**: Rate limited by LingQ API.

**Solution**:
- The add-on automatically retries with backoff
- If persistent, wait 5-10 minutes before retrying
- Reduce sync frequency

#### "Note type not found"

**Cause**: The `note_type` in your profile doesn't exist in Anki.

**Solution**:
1. Open Anki → Tools → Manage Note Types
2. Verify the exact name of your note type
3. Update profile configuration to match exactly (case-sensitive)

#### "Field not found"

**Cause**: A field in `field_mapping` doesn't exist on the note type.

**Solution**:
1. Open Anki → Tools → Manage Note Types → Fields
2. Verify field names match your configuration exactly
3. Update profile to use correct field names

#### Large Number of Conflicts

**Cause**: Many ambiguous matches, often due to:
- Common words with multiple meanings
- Incomplete LingQ hints
- Mismatched translation fields

**Solution**:
1. Review conflict details in dry-run output
2. Add more specific hints in LingQ
3. Use more descriptive translations in Anki
4. Accept that some conflicts are unavoidable (polysemy)

#### Sync Seems Stuck

**Cause**: Large vocabulary or slow network.

**Solution**:
1. Check Anki's progress indicator
2. LingQ API pagination may take time for large collections
3. If truly stuck, close dialog and check checkpoint file
4. Resume will continue from last checkpoint

#### Checkpoint File Corruption

**Cause**: Interrupted sync or file system issues.

**Solution**:
1. Delete the checkpoint file: `.lingq_sync_checkpoint_{profile_name}.json`
2. Run a fresh dry-run
3. Apply changes from the beginning

### Debug Logging

To enable verbose logging:

1. Open Anki with debug console: `anki --debug`
2. Or check Anki's log file location for your OS
3. Look for lines starting with `LingQ request` and `LingQ response`

### Getting Help

If issues persist:

1. Collect relevant information:
   - Anki version
   - Add-on version
   - Error messages (redact any tokens!)
   - Dry-run output
2. Check existing issues on the project repository
3. Open a new issue with collected information

---

## Quick Reference

### LingQ Status Codes

| Status | Meaning |
|--------|---------|
| 0 | New (never reviewed) |
| 1 | Recognized |
| 2 | Familiar |
| 3 | Learned |
| 4 | Known (mastered) |

### Operation Types

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `create_anki` | LingQ → Anki | Create new Anki note |
| `create_lingq` | Anki → LingQ | Create new LingQ card |
| `link` | Bidirectional | Link existing items |
| `update_hints` | Anki → LingQ | Update LingQ hints |
| `update_status` | Anki → LingQ | Update LingQ status |
| `reschedule_anki` | LingQ → Anki | Adjust Anki scheduling |
| `conflict` | — | Ambiguous, skipped |
| `skip` | — | Policy skip (polysemy) |

### Language Codes (Common)

| Code | Language |
|------|----------|
| `en` | English |
| `sv` | Swedish |
| `de` | German |
| `fr` | French |
| `es` | Spanish |
| `ja` | Japanese |
| `ko` | Korean |
| `zh` | Chinese |

See LingQ documentation for the complete list.
