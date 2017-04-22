import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

import deform
import colander

import uuid
from .phrase_groups import process_phrase
from .phrase_storage import PhraseStorage

from .op_messages import (
    parse_messages,
    MessageType,
    OpMessage
)

max_active_groups = 250
phrase_storage = PhraseStorage(max_active_groups)

class PhraseForm(colander.Schema):
    phrases = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(max=10000),
        widget=deform.widget.TextAreaWidget(rows=10, cols=60),
        description='Enter the phrase templates, one per line'
    )
    seed = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(max=150),
        missing='',
        description=(
            'Optional: seed for a repeatable set of random choices, leave '
            'blank to use current time'
        )
    )

class PhrasalViews(object):
    def __init__(self, request):
        self.request = request

    @property
    def phrase_form(self):
        schema = PhraseForm()
        return deform.Form(schema, buttons=('submit', 'clear', 'demo'))

    @property
    def reqts(self):
        return self.phrase_form.get_widget_resources()

    @property
    def session_uuid(self):
        session = self.request.session

        active_uuid = ''
        if 'phrase_group_uuid' not in session:
            active_uuid = uuid.uuid4()
            log.info("session: Creating new UUID {0}".format(active_uuid))
            session['phrase_group_uuid'] = active_uuid
        else:
            active_uuid = session['phrase_group_uuid']

        return active_uuid

    @property
    def session_was_lost(self):
        session = self.request.session
        if 'session_reset' not in session:
            # Wasn't tracked before, assume a fresh visitor
            log.debug(
                "session_was_lost: Setting session reset status to: {0}"
                .format(False)
            )
            self.session_was_lost = False
            return False
        # Get the value of the session_reset state
        return session['session_reset']

    @session_was_lost.setter
    def session_was_lost(self, value):
        session = self.request.session
        log.debug(
            "session_was_lost: Setting session reset status to: {0}"
            .format(value)
        )
        session['session_reset'] = value

    def session_check_reset(self):
        # Check if the session UUID exists
        session = self.request.session
        # Do we have a session UUID?
        if 'phrase_group_uuid' in session:
            # Does storage -not- have it?
            if not phrase_storage.has_phrase_group(self.session_uuid):
                # We've lost the session
                log.warn(
                    "session_check_reset: Session '{0}' was lost"
                    .format(str(self.session_uuid))
                )
                self.session_was_lost = True

    @property
    def phrase_group(self):
        # Check if the phrase group is missing before potentially creating a
        # new one
        self.session_check_reset()
        return phrase_storage.get_phrase_group(self.session_uuid)

    @phrase_group.setter
    def phrase_group(self, value):
        # Check if the phrase group is missing before potentially creating a
        # new one
        self.session_check_reset()
        phrase_storage.set_phrase_group(self.session_uuid, value)

    @property
    def msgs(self):
        return self.phrase_group['msgs']

    @msgs.setter
    def msgs(self, value):
        if isinstance(value, list):
            log.debug("msgs: Storing list messages of {0}".format(value))
        else:
            log.debug("msgs: Storing single messages of {0}".format(value))
            # Encapulsate the value in a list
            value = [ value ]
        self.phrase_group['msgs'] = value

    @view_config(route_name='phrasal_form_view', renderer='templates/phrase_generate_form.pt')
    def phrasal_form_view(self):
        phrase_group = self.phrase_group
        phrase_form = self.phrase_form

        if 'POST' in self.request.method:
            # If posting, no data would've been persisted anyways
            # NOTE: If this changes in the future, remove it from here!
            self.session_was_lost = False
            # Clear temporary data if it's a post
            self.msgs = []

        if self.session_was_lost:
            self.msgs.append(
                OpMessage(
                    MessageType.Info,
                    "Your browser says you've visited, but I don't remember "
                    "what you wrote.  The server might've been restarted.  "
                    "Pardon for any hassle.",
                    "Welcome back!"
                )
            )
            self.session_was_lost = False

        if 'clear' in self.request.params:
            log.debug(
                "phrasal_form_view: Clearing UUID {0}"
                .format(self.session_uuid)
            )
            phrase_group['seed'] = ''
            phrase_group['phrases'] = ''
            phrase_group['results'] = ''
            # Shift focus to the form
            url = self.request.route_url(
                'phrasal_form_view', _anchor='form'
            )
            return HTTPFound(url)
        elif 'demo' in self.request.params:
            log.debug(
                "phrasal_form_view: Resetting UUID {0} to demo"
                .format(self.session_uuid)
            )
            phrase_group['seed'] = ''
            phrase_group['phrases'] = PhraseStorage.get_demo_phrase_source()
            phrase_group['results'] = ''
            self.msgs.append(
                OpMessage(
                    MessageType.Info,
                    "Read the phrases above and press Submit to see the "
                    "results.",
                    "Demo ready"
                )
            )
            # Shift focus to the form
            url = self.request.route_url(
                'phrasal_form_view', _anchor='form'
            )
            return HTTPFound(url)
        elif 'submit' in self.request.params:
            controls = self.request.POST.items()
            try:
                appstruct = phrase_form.validate(controls)
            except deform.ValidationFailure as e:
                return dict(
                    phrase_group=phrase_group,
                    form=e.render()
                )

            # Change the content and redirect to the view
            phrase_group['seed'] = appstruct['seed']
            phrase_group['phrases'] = appstruct['phrases']
            # Process the source, get the results
            phrase_group['results'] = (
                process_phrase(
                    self.msgs,
                    phrase_group['phrases'],
                    phrase_group['seed']
                )
            )
            log.debug(
                "phrasal_form_view: Updating UUID {0}, new group {1}"
                .format(self.session_uuid, phrase_group)
            )
            self.phrase_group = phrase_group

            url = self.request.route_url(
                'phrasal_form_view', _anchor='results'
            )
            return HTTPFound(url)

        form = phrase_form.render(phrase_group)

        parsed_msgs = parse_messages(self.msgs)
        if parsed_msgs:
            log.debug(
                "phrasal_form_view: parsed_msgs: '{0}'"
                .format(parsed_msgs)
            )

        return dict(
            phrase_group=phrase_group, parsed_msgs=parsed_msgs, form=form
        )
