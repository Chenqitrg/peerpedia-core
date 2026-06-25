# Social Recovery Design Proposal

Moved from `peerpedia_core/commands/users.py` TODO(social-recovery) on 2026-06-25.

## Problem

If a user loses their device AND their salt (the only recovery path is
password+salt), they are permanently locked out — all articles, follows,
reputation are irrecoverable.

## Proposed Protocol

Needs a social recovery protocol:

1. User pre-designates N trusted recovery guardians (mutual follows).
2. Guardians each hold an encrypted key shard (Shamir's secret sharing
   or threshold signatures, M-of-N).
3. On recovery: M guardians confirm the request → reconstruct the
   private key.  The new key is pushed via `push_key_rotation`.
4. Guardians must be online peers — the protocol is P2P, not
   centralized.  No single guardian can unilaterally recover.

## Requirements

- Guardian model (DB schema for recovery relationships)
- Shard protocol (Shamir's secret sharing implementation)
- Recovery CLI (`peerpedia account recover --social`)
- P2P messaging (guardian confirmation transport)

## Relationship to multi-device bootstrap

This design is orthogonal to the multi-device bootstrap flow (`account
bootstrap` + `account recover`).  Bootstrap handles "new device, known
password + salt."  Social recovery handles "lost everything — device,
salt, and potentially password."  Bootstrap is implemented; social
recovery is deferred.

## Implementation Site

`peerpedia_core/commands/users.py` — the `update_user_public_key` function
is the likely integration point for key rotation after social recovery.
