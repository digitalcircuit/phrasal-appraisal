import logging
log = logging.getLogger(__name__)

import copy

from collections import deque

# Store phrases
class PhraseStorage(object):
    # Static variables
    demo_phrase_source = (
        "{John|Jane} goes to {school|work}.\n"
        "{Alice|Bob} prefers to work {alone|in teams{| with friends}}.\n"
        "\n"
        "# Tutorial and tips\n"
        "Tap Submit to give it a try, click again for another phrase!\n"
        "#\n"
        "You can make groups with '#', optionally giving it a name.\n"
        "One phrase is chosen from each group.\n"
        "For example, there's three phrases in this group.  Only one of "
        "these three will {survive|show up} in the results.\n"
        "\n"
        "# More advanced phrasing\n"
        "The weather outside {today|tomorrow} will {un|}fortunately be quite "
        "{cheery|gloomy|calm}.\n"
        "Sometimes I {don't|} like to {eat {pie|pizza}|"
        "read {{{very {absurdly {ludicrously {nonsensically {insanely "
        "{maximally|magically} |}|}|}|}|}long|short}manuals|books}}.\n"
        "\\# Lines can start with '\\#' (but '#' doesn't need escaped except "
        "at the start), literal {\\{brackets\\}|\\{squiggly braces\\}} and "
        "\\|pipes\\| work,  too.\n"
        "\n"
        "# A story snippet\n"
        "In quia quis reprehenderit. Culpa impedit quia nulla ipsum quis "
        "recusandae repellat. Et ut velit rem. Quas libero rerum non nemo. A "
        "velit ut porro. Quia aperiam rem error temporibus corrupti.\n"
        "{The Dormouse had closed its eyes by this time, and was going off "
        "into  a doze; but, on being pinched by the Hatter, it woke up again "
        "with  a little shriek, and went on: '-that begins with an M, such "
        "as  mouse-traps, and the moon, and memory, and muchness-you know "
        "you say  things are \"much of a muchness\"-did you ever see "
        "such a thing as a  drawing of a muchness?'|Phileas Fogg and Aouda "
        "went on board, where they found Fix already installed. Below deck "
        "was a square cabin, of which the walls bulged out in the form of "
        "cots, above a circular divan; in the centre was a table provided "
        "with a swinging lamp. The accommodation was confined, but neat.} "
        "-- http://www.fillerati.com/"
    )

    default_phrase_group = dict(
        uid='100', seed='', title='Default',
        source='', results='', msgs=[]
    )

    def __init__(self, max_active_groups):
        self.max_active_groups = max_active_groups
        self.active_phrase_groups = deque()
        self.phrase_groups = {}

    @staticmethod
    def get_default_phrase_group():
        # Deep copy to avoid linking items
        return copy.deepcopy(PhraseStorage.default_phrase_group)

    @staticmethod
    def get_demo_phrase_source():
        return PhraseStorage.demo_phrase_source

    def has_phrase_group(self, active_uuid):
        return active_uuid in self.phrase_groups

    def get_phrase_group(self, active_uuid):
        if active_uuid not in self.phrase_groups:
            # Clean up old groups
            while ((len(self.phrase_groups) + 1) > self.max_active_groups
                    and len(self.active_phrase_groups) > 0):
                # Remove the oldest first
                old_uuid = self.active_phrase_groups.popleft()
                log.info("storage: Deleting old group {0}"
                    .format(old_uuid)
                )
                del self.phrase_groups[old_uuid]

            # Track this group
            log.info("storage: Adding new group {0}".format(active_uuid))
            self.active_phrase_groups.append(active_uuid)
            # Clone the default phrase group
            self.phrase_groups[active_uuid] = (
                PhraseStorage.get_default_phrase_group()
            )
            self.phrase_groups[active_uuid]['uid'] = active_uuid
            # TODO: Better auto-generated titles
            self.phrase_groups[active_uuid]['title'] = active_uuid

        desired_group = self.phrase_groups[active_uuid]
        log.debug("storage: Getting group {0} of {1}"
            .format(active_uuid, desired_group)
        )
        return desired_group

    def set_phrase_group(self, active_uuid, phrase_group):
        log.debug("storage: Setting group {0} to {1}"
            .format(active_uuid, phrase_group)
        )
        self.phrase_groups[active_uuid] = phrase_group
