"""Message ids the build ALLOCATES: a chapter names the messages it needs, the build numbers them.

Every hosted chapter used to pick literal ids out of a dead vanilla block, and a full block made
the next scene a redesign (ch05 spent all 18 of 0x9E4-0x9F5). This is pokeemerald's
`map_event_ids.h` move instead: a chapter declares its messages BY NAME here, and each gets an id
appended past vanilla's last message (MSG_D4B). gMsgTable[] is generated from texts.txt and
self-sizes, so the table has no budget to run out of.

The ids are a pure function of this ledger: chapters in campaign order, each a contiguous run in
the order it lists its names. So adding a message to an earlier chapter renumbers the later ones,
and that is safe because nothing outside the build names an appended id -- read one through
`appended_message_id`, never write the number down.

The dead-block ids chapters already ship stay where they are (`HOSTED_CHAPTER_MESSAGE_BLOCKS`):
renumbering a shipped vanilla-range id changes the ROM for no gain. A NEW message is a name here.

Stdlib only and a leaf: `inject.chapter_ids` imports it.
"""
import re
import sys

# The size of vanilla's message table (gMsgTable). Ids at or above this are ours, appended.
VANILLA_MESSAGE_COUNT = 0xD4C

# {chapter: (message name, ...)}. Order within a chapter is the allocation order; the order of
# the chapters here is not (they allocate in campaign order whatever this dict says).
APPENDED_MESSAGES = {
    # Wolfram's turn-1 call-out of the forts' and the gate's healing (#21, #135 finding 8).
    'ch01': ('terrain-heal-warning',),
    # The moose's NAME (#25). A raw pid's stock nameTextId is the generic monster plate every
    # 0xB0-range gap shares, so it can never be retitled for one creature.
    'ch05': ('moose-name',),
    # The two boats' name plates (#360), one each so the boarding pass can name the Burly Ram
    # and the Pronged Goat apart.
    'ch06': ('boat-east-name', 'boat-west-name'),
}


_CHAPTER_KEY = re.compile(r'^ch\d\d$')


def allocated_message_ids(ledger=None):
    """{(chapter, name): message id} for every appended message."""
    ledger = APPENDED_MESSAGES if ledger is None else ledger
    out = {}
    next_id = VANILLA_MESSAGE_COUNT
    for chapter in sorted(ledger):
        # `chNN` (the prologue is ch00, as in HOSTED_CHAPTER_MESSAGE_IDS) is what makes a sort
        # by name a sort by campaign order.
        if not _CHAPTER_KEY.match(chapter):
            sys.exit('ERROR: APPENDED_MESSAGES key %r is not a chNN chapter id (the prologue is '
                     'ch00)' % (chapter,))
        seen = set()
        for name in ledger[chapter]:
            if name in seen:
                sys.exit('ERROR: %s declares appended message %r twice in APPENDED_MESSAGES; '
                         'a name is one message' % (chapter, name))
            seen.add(name)
            out[(chapter, name)] = next_id
            next_id += 1
    return out


def appended_message_id(chapter, name, ledger=None):
    """The id the build allocated to `chapter`'s message `name`."""
    ids = allocated_message_ids(ledger)
    if (chapter, name) not in ids:
        sys.exit('ERROR: %s has no appended message %r -- declare it in '
                 'inject/message_alloc.py APPENDED_MESSAGES' % (chapter, name))
    return ids[(chapter, name)]
