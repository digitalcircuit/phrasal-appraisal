import logging
log = logging.getLogger(__name__)

from abc import ABCMeta, abstractmethod

import random

# Track time to avoid potential infinite loops
from .time_limiter import (
    TimeLimiter,
    TimeoutException
)

from .op_messages import (
    MessageType,
    OpMessage
)


# Process the requested phrase
def process_phrase(msgs, phrase_set, seed = ''):
    # Seed the random number generator.  We don't need cryptographic security.
    if seed:
        log.debug("process_phrase: Setting random seed to {0}".format(seed))
        random.seed(seed)
    else:
        log.debug("process_phrase: Setting random seed to default")
        random.seed()

    log.debug(
        "process_phrase: Processing phrase set: '{0}'"
        .format(phrase_set)
    )
    # Process the given phrases
    # Don't allow this to run on indefinitely
    time_limit = TimeLimiter(0.5)
    try:
        # Parse the input phrases
        phrases_raw = process_phrase_sections(msgs, time_limit, phrase_set)
        # Check time in between processing and grabbing
        time_limit.check()
        # Select a set of phrases and apply the random selections
        chosen_phrases = select_phrases(msgs, time_limit, phrases_raw)
        log.debug(
            "process_phrase: Picked phrases: '{0}'"
            .format(chosen_phrases)
        )
    except TimeoutException as e:
        # Clear any chosen phrases
        chosen_phrases = []
        log.error(
            "process_phrase: Exceeded time limit of '{0}': {1}"
            .format(time_limit.limit_sec, e),
            exc_info = True
        )
        msgs.append(
            OpMessage(
                MessageType.Danger,
                "Check for misplaced brackets, or if the phrases look "
                "complex.  It's possible there's a bug in this app.",
                "Ran out of time",
                "Stopping since this is taking more than {0} seconds."
                .format(time_limit.limit_sec)
            )
        )
    except Exception as e:
        # Clear any chosen phrases
        chosen_phrases = []
        log.error(
            "process_phrase: Ran into a generic exception: {1}"
            .format(e),
            exc_info = True
        )
        msgs.append(
            OpMessage(
                MessageType.Danger,
                "Check for misplaced brackets, or if the phrases look "
                "complex.  It's possible there's a bug in this app.",
                "Something unexpected happened",
                "Ran into an unexpected exception while building phrases."
            )
        )

    return chosen_phrases

def process_phrase_sections(msgs, time_limit, groups):
    # Switch to '\n' only for new lines
    groups = groups.replace('\r', '')

    current_title = ''

    # Split
    phrases_string = groups.split('\n')
    log.debug(
        "process_phrase_sections: Given {0} potential phrase entries"
        .format(len(phrases_string))
    )
    groups_raw = []
    current_group = []
    for phrase_line in phrases_string:
        if not phrase_line.strip():
            continue
        if phrase_line.startswith('#'):
            log.debug(
                "process_phrase_sections: Found a new group in line: '{0}'"
                .format(phrase_line)
            )
            # This marks a new phrase group
            if current_group:
                log.debug(
                    "process_phrase_sections: Saving prior group '{0}' with "
                    "{1} entries"
                    .format(current_title, len(current_group))
                )
                # Add all existing to a new entry
                groups_raw.append({
                    'title': current_title,
                    'phrases': current_group
                })
                # Reset the current group
                current_group = []
            # Grab the group title
            # Skip over the '#' symbol, then remove any leading whitespace
            current_title = phrase_line[1:].lstrip(" ")
        else:
            log.debug(
                "process_phrase_sections: Adding regular line to current "
                "group '{0}', line: '{1}'"
                .format(current_title, phrase_line)
            )
            # Add to the existing group
            current_group.append(phrase_line)

    # Finish up the current group, if any
    if current_group:
        log.debug(
            "process_phrase_sections: Saving final group '{0}' with {1}"
            "entries"
            .format(current_title, len(current_group))
        )
        # Add all existing to a new entry
        groups_raw.append({
            'title': current_title,
            'phrases': current_group
        })

    return groups_raw

def select_phrases(msgs, time_limit, raw_phrases):
    phrases_processed = []
    log.debug(
        "select_phrases: Given {0} phrase groups to process"
        .format(len(raw_phrases))
    )
    
    phrases_warned = []

    # For each group of phrases
    for raw_phrase_group in raw_phrases:
        # Pick a random phrase in the group
        group_title = raw_phrase_group['title']
        raw_phrase = random.choice(raw_phrase_group['phrases'])
        log.debug(
            "select_phrases: In group '{0}', picked phrase: '{1}'"
            .format(group_title, raw_phrase)
        )
        # Process the raw phrase into a bunch of PhrasePart objects
        # Track any warning messages
        process_warn_details = []
        chosen_phrase = flatten_phrase(
            process_phrase_part(process_warn_details, time_limit, raw_phrase)
        )
        if process_warn_details:
            # Something went wrong, but didn't crash.  Queue a message for it.
            phrases_warned.append({
                'phrase': raw_phrase,
                'details': process_warn_details
            })

        # Add phrase to the list of processed phrases
        phrases_processed.append({
            'title': group_title,
            'result': chosen_phrase
        })

    # Check for trouble situations
    if phrases_warned:
        # At least one phrase had trouble being processed.  Build a message.
        warning_details = []
        for phrase_warned in phrases_warned:
            # Convert the details to a friendly list
            friendly_details = ''
            for warning_detail in phrase_warned['details']:
                friendly_details += " > {0}\n".format(warning_detail)
            # Remove extra spaces at the end
            friendly_details = friendly_details.rstrip()
            # Create a friendly overview message
            warning_details.append(
                "Trouble with:\n\t\"{0}\"\nReasons:\n{1}"
                .format(phrase_warned['phrase'], friendly_details)
            )
        msgs.append(
            OpMessage(
                MessageType.Warn,
                "Something went wrong while building your phrases.  Double-"
                "check that you have the right number of brackets and pipes.  "
                "Check the Demo for some examples.",
                "Trouble building phrases",
                warning_details
            )
        )

    log.debug(
        "select_phrases: Processed {0} phrase groups"
        .format(len(phrases_processed))
    )
    # Hand 'em over
    return phrases_processed

def flatten_phrase(phrase_parts):
    phrase_array = []
    if isinstance(phrase_parts, list):
        for phrase_base_part in phrase_parts:
            phrase_array.extend(flatten_phrase(phrase_base_part))
    else:
        phrase_result = phrase_parts.result
        if isinstance(phrase_result, list):
            for phrase_base_part in phrase_result:
                phrase_array.extend(flatten_phrase(phrase_base_part))
        else:
            phrase_array.append({
                'choice_level': phrase_parts.choice_level,
                'result': phrase_result
            })

    return phrase_array

def strip_escape_chars(phrase_result):
    # Remove phrase escape characters
    #   \{ -> {
    #   \} -> }
    #   \| -> |
    #   \# -> #
    #   \\ -> \
    phrase_unescaped = phrase_result.replace("\\{", "{") \
        .replace("\\}", "}").replace("\\|", "|")         \
        .replace("\\#", "#").replace("\\\\", "\\")
    return phrase_unescaped

def skip_escape_char(phrase, start_index):
    if start_index < 0 or start_index > len(phrase):
        log.debug(
            "skip_escape_char: start_index of {0} is out of range, "
            "phrase length is {1}"
            .format(start_index - 1, len(phrase))
        )
        return start_index
    if phrase[start_index - 1] is '\\':
        log.debug(
            "skip_escape_char: Found escape code at {0}, "
            "advancing by one manually"
            .format(start_index - 1)
        )
        start_index += 1
    return start_index
    

def process_phrase_part(msg_details, time_limit, phrase, choice_level = 0):
    log.debug(
        "process_phrase_part: [ENTER] Phrase is: '{0}'"
        .format(phrase)
    )
    if '{' not in phrase:
        # Handle non-bracketed text
        # E.g. "Some text."
        log.debug(
            "process_phrase_part: [EXIT] No '{{' found, adding "
            "PhraseSinglePart: '{0}'"
            .format(phrase)
        )
        return PhraseSinglePart(strip_escape_chars(phrase), choice_level)

    # Reference from
    # https://stackoverflow.com/questions/15717436/js-regex-to-match-everything-inside-braces-including-nested-braces-i-want/27088184#27088184
    # Set up
    phrase_parts = []
    cur_pos = 0
    start_index = phrase.index("{")
    escaped_start_index = skip_escape_char(phrase, start_index)
    # Only process beginning differently if not escaped

    if (start_index > 0 and escaped_start_index is start_index):
        # Handle non-bracketed text at the beginning
        # E.g. "Some {text|non-text}"
        phrase_begin = phrase[0:start_index]
        log.debug(
            "process_phrase_part: Found text from 0 to {0}, "
            "adding begin PhraseSinglePart: '{1}'"
            .format(start_index, phrase_begin)
        )
        phrase_parts.append(
            PhraseSinglePart(strip_escape_chars(phrase_begin), choice_level)
        )
        cur_pos = start_index

    # Handle all brackets
    # Check up until end of string
    open_brackets = 0

    loop_counter = 0
    while (cur_pos < len(phrase)):
        # Check time to avoid infinite loops, but don't always check to reduce
        # performance impact.
        if loop_counter > 100:
            loop_counter = 0
            time_limit.check()
        else:
            loop_counter += 1

        if '{' not in phrase[cur_pos:]:
            log.debug(
                "process_phrase_part: No more brackets left at {0} out of {1}"
                .format(cur_pos, len(phrase))
            )
            # No more brackets left
            break

        start_index = phrase.index("{", cur_pos)
        escaped_start_index = skip_escape_char(phrase, start_index)
        if start_index != escaped_start_index:
            # Check after any skipped escape character
            log.debug(
                "process_phrase_part: Found middle escape character at {0}"
                .format(escaped_start_index)
            )
            if '{' not in phrase[escaped_start_index:]:
                # No more
                break
            escaped_start_index = phrase.index("{", escaped_start_index)

        log.debug(
            "process_phrase_part: Searching for '{{' at {0}, found at {1}"
            .format(cur_pos, start_index)
        )
        
        if start_index > 0 and (cur_pos + 1) < start_index:
            # Handle non-bracketed text at the middle
            # E.g. "Some {text|non-text} here {there}"
            phrase_middle = phrase[cur_pos:start_index]
            log.debug(
                "process_phrase_part: Found text from {0} to {1}, "
                "adding middle PhraseSinglePart: '{2}'"
                .format(cur_pos + 1, start_index, phrase_middle)
            )
            phrase_parts.append(
                PhraseSinglePart(
                    strip_escape_chars(phrase_middle), choice_level
                )
            )
            cur_pos = start_index
        
        # Apply escaping
        start_index = escaped_start_index

        # Find all brackets
        cur_pos = start_index
        loop_counter_inner = 0
        while (cur_pos < len(phrase)):
            # Check time to avoid infinite loops, but don't always check to reduce
            # performance impact.
            if loop_counter_inner > 100:
                loop_counter_inner = 0
                time_limit.check()
            else:
                loop_counter_inner += 1
            # Grab the current character
            cur_char = phrase[cur_pos]
            if cur_char is '\\':
                # Skip the current and next character
                log.debug(
                    "process_phrase_part: Skipping escape char at {0}"
                    .format(cur_pos)
                )
                cur_pos += 2
                continue

            if cur_char is '{':
                open_brackets += 1
                log.debug(
                    "process_phrase_part: Found '{{' at {0}, {1} open brackets"
                    .format(cur_pos, open_brackets)
                )
            elif cur_char is '}':
                open_brackets -= 1
                log.debug(
                    "process_phrase_part: Found '}}' at {0}, {1} open brackets"
                    .format(cur_pos, open_brackets)
                )

            if open_brackets is 0:
                # Found a complete section, parse it
                # Add +1 to start_index to skip the given character
                phrase_contents = phrase[start_index + 1:cur_pos]
                cur_pos = start_index + 1 + len(phrase_contents)
                log.debug(
                    "process_phrase_part: Found complete section at {0} to "
                    "{1}, contents: '{2}'"
                    .format(start_index + 1, cur_pos, phrase_contents)
                )
                phrase_parts.append(
                    process_phrase_subsections(
                        msg_details, time_limit, phrase_contents,
                        choice_level + 1
                    )
                )
                # Found, escape out to check for others
                # Go to the next character
                cur_pos += 1
                break

            # Go to the next character
            cur_pos += 1

    if open_brackets is not 0:
        # A bracket wasn't closed somewhere.  Reset from start_index, treat
        # as if it's a regular phrase.
        log.warn(
            "process_phrase_part: Open brackets is {0}, expected zero.  "
            "Missing bracket maybe?  Resetting cur_pos from {1} to {2}"
            .format(open_brackets, cur_pos, start_index)
        )
        msg_details.append(
            "Open brackets is {0}, expected zero by {1}, check near {2}.  "
            "Too many open/missing close brackets, maybe?"
            .format(open_brackets, cur_pos, start_index)
        )
        cur_pos = start_index

    if cur_pos < len(phrase):
        # Handle any dangling non-bracketed text
        # E.g. "{text|non-text} here"
        phrase_end = phrase[cur_pos:]
        if (cur_pos + 1 == len(phrase)) and phrase_end is '}':
            log.debug(
                "process_phrase_part: Reached {0} out of {1} characters, but "
                "last character is a '}}'.  Skipping '}}'."
                .format(cur_pos, len(phrase))
            )
        else:
            log.debug(
                "process_phrase_part: Reached {0} out of {1} characters,"
                " adding end PhraseSinglePart: '{2}'"
                .format(cur_pos, len(phrase), phrase_end)
            )
            phrase_parts.append(
                PhraseSinglePart(strip_escape_chars(phrase_end), choice_level)
            )

    log.debug(
        "process_phrase_part: [EXIT] Finished processing phrase: '{0}'"
        .format(phrase)
    )
    
    return phrase_parts

def process_phrase_subsections(
        msg_details, time_limit, phrase_subsections, choice_level):
    # Handle splitting up sections inside a phrase
    # Need to handle escaped '|' symbols
    log.debug(
        "process_phrase_subsections: [ENTER] Phrase subsections are: '{0}'"
        .format(phrase_subsections)
    )

    if '|' not in phrase_subsections:
        # Handle text
        # E.g. "Some text."
        log.debug(
            "process_phrase_subsections: No '|' found, processing "
            "phrase: '{0}'"
            .format(phrase_subsections)
        )
        return process_phrase_part(
            msg_details, time_limit, phrase_subsections, choice_level
        )

    phrase_subsections += "|"
    log.debug(
        "process_phrase_subsections: Adding extra '|' for processing, new "
        "result: '{0}'"
        .format(phrase_subsections)
    )

    open_brackets = 0
    split_start = 0 #phrase_subsections.index("|")
    split_pos = 0
    split_entries = []
    split_last_empty = False

    loop_counter = 0

    while (split_pos < len(phrase_subsections)):
        # Check time to avoid infinite loops, but don't always check to reduce
        # performance impact.
        if loop_counter > 100:
            loop_counter = 0
            time_limit.check()
        else:
            loop_counter += 1

        # Grab the current character
        cur_char = phrase_subsections[split_pos]
        
        if cur_char is '\\':
            # Skip the current and next character
            split_pos += 2
            continue

        if cur_char is '{':
            open_brackets += 1
            log.debug(
                "process_phrase_subsections: Found '{{' at {0}, {1} open "
                "brackets"
                .format(split_pos, open_brackets)
            )
        elif cur_char is '}':
            open_brackets -= 1
            log.debug(
                "process_phrase_subsections: Found '}}' at {0}, {1} open "
                "brackets"
                .format(split_pos, open_brackets)
            )

        if cur_char is '|':
            if open_brackets is not 0:
                # Skip the current character
                log.debug(
                    "process_phrase_subsections: Found '|' at {0} with open "
                    "bracket level {1}, ignoring"
                    .format(split_pos, open_brackets)
                )
            else:
                # New split detected
                # Found a complete section, parse it
                # Add +1 to start_index to skip the given character, unless
                # it's the first run.
                if split_start is not 0 or split_last_empty:
                    log.debug(
                        "process_phrase_subsections: Skipping split start "
                        "ahead from {0} to {1}, split_last_empty = {2}, prior "
                        "contents: '{3}'"
                        .format(
                            split_start, split_start + 1, split_last_empty,
                            phrase_subsections[split_start:split_pos]
                        )
                    )
                    split_start += 1
                phrase_piece = phrase_subsections[split_start:split_pos]
                split_pos = split_start + len(phrase_piece)
                log.debug(
                    "process_phrase_subsections: Found complete section at "
                    "{0} to {1}, contents: '{2}'"
                    .format(split_start, split_pos, phrase_piece)
                )
                split_entries.append(
                    process_phrase_part(
                        msg_details, time_limit, phrase_piece, choice_level
                    )
                )
                if (split_start is 0 and split_pos is 0):
                    # Special case for "{|some string}" when the first is
                    # picked.
                    split_last_empty = True
                    log.debug(
                        "process_phrase_subsections: Included blank from "
                        "start of string complete section"
                    )
                else:
                    split_last_empty = False

                # Added split, don't try to add from it again
                split_start = split_pos

        # Go to the next character
        split_pos += 1

    if open_brackets is not 0:
        # A bracket wasn't closed somewhere.
        log.warn(
            "process_phrase_subsections: Open brackets is {0}, expected "
            "zero."
            .format(open_brackets)
        )
        msg_details.append(
            "Open brackets is {0}, expected zero.  "
            "Too many open/missing close brackets, maybe?"
            .format(open_brackets)
        )

    if split_pos < len(phrase_subsections):
        # Grab the last entry
        # It might be a blank entry, e.g. {word|} would have a blank at end
        phrase_end = phrase_subsections[split_pos:]
        log.debug(
            "process_phrase_subsections: Reached {0} out of {1} characters, "
            "processing end phrase: '{2}'"
            .format(split_pos, len(phrase_subsections), phrase_end)
        )
        split_entries.append(
            process_phrase_part(
                msg_details, time_limit, phrase_end, choice_level
            )
        )

    log.debug(
        "process_phrase_subsections: [EXIT] Finished processing phrase "
        "subsections: '{0}'"
        .format(phrase_subsections))

    return PhraseMultiPart(split_entries, choice_level)

# Keep phrases
class PhrasePart(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def choice_level(self): raise NotImplementedError

    @abstractmethod
    def result(self): raise NotImplementedError

class PhraseSinglePart(PhrasePart):
    def __init__(self, phrase, choice_level = 0):
        self.phrase = phrase
        self.choice_level_internal = choice_level
        log.debug(
            "PhraseSinglePart: Creating new at depth {0}, from phrase: '{1}'"
            .format(choice_level, phrase)
        )

    @property
    def choice_level(self):
        return self.choice_level_internal

    @property
    def result(self):
        return self.phrase

    def __str__(self):
        return self.phrase

class PhraseMultiPart(PhrasePart):
    def __init__(self, phrases, choice_level = 0):
        self.phrases = phrases
        self.choice_level_internal = choice_level
        log.debug(
            "PhraseMultiPart: Creating new at depth {0}, from {1} "
            "phrases: '{2}'"
            .format(choice_level, len(phrases), str(phrases))
        )

    @property
    def choice_level(self):
        return self.choice_level_internal

    @property
    def result(self):
        phrase_result = random.choice(self.phrases)
        return random.choice(self.phrases)

    def __str__(self):
        result_str = ''
        for phrase_entry in self.phrases:
            if isinstance(phrase_entry, PhraseMultiPart):
                result_str += "{0}, ".format(str(phrase_entry))
            else:
                result_str += "'{0}', ".format(str(phrase_entry))
        # Remove the trailing space and comma
        return "[{0}]".format(result_str[:-2])
