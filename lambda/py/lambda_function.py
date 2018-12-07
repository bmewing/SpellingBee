# -*- coding: utf-8 -*-

# This is a High Low Guess game Alexa Skill.
# The skill serves as a simple sample on how to use the
# persistence attributes and persistence adapter features in the SDK.
import random
import logging
import os
import requests
import json
import re

from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

SKILL_NAME = 'Spelling Bee Plus'
sb = StandardSkillBuilder(table_name="Spelling-Bee-Game", auto_create_table=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    """Handler for Skill Launch.

    Get the persistence attributes, to figure out the game state.
    """
    # type: (HandlerInput) -> Response
    attr = handler_input.attributes_manager.persistent_attributes
    if not attr:
        attr['ended_session_count'] = 0
        attr['games_played'] = 0
        attr['game_state'] = 'ENDED'

    handler_input.attributes_manager.session_attributes = attr

    speech_text = (
        "Welcome to the Spelling Bee game. You have played {} times. "
        "Would you like to play?".format(attr["games_played"]))
    reprompt = "Say yes to start the game or no to quit."

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    """Handler for Help Intent."""
    # type: (HandlerInput) -> Response
    speech_text = (
        "I ask you to spell words to help you practice. You can ask me to provide definitions, use the word in a "
        "sentence or repeat the word. When you're ready, say 'spelling' and then spell the word. I'll ask you to "
        "confirm the spelling and then let you know if you're right.")
    reprompt = "Try asking for a definition."

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(
    can_handle_func=lambda input:
        is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    """Single handler for Cancel and Stop Intent."""
    # type: (HandlerInput) -> Response
    speech_text = "Thanks for playing!!"

    handler_input.response_builder.speak(
        speech_text).set_should_end_session(True)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    """Handler for Session End."""
    # type: (HandlerInput) -> Response
    logger.info(
        "Session ended with reason: {}".format(
            handler_input.request_envelope.request.reason))
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    not currently_playing(input) and
                    is_intent_name("AMAZON.YesIntent")(input))
def yes_handler(handler_input):
    """Handler for Yes Intent, only if the player said yes for
    a new game.
    """
    # type: (HandlerInput) -> Response
    secure_random = random.SystemRandom()
    words = ['happy', 'sad']
    session_attr = handler_input.attributes_manager.session_attributes
    session_attr['game_state'] = "STARTED"
    session_attr['word'] = secure_random.choice(words)

    speech_text = "Please spell {0}.".format(session_attr['word'])
    reprompt = "Please spell {0}.".format(session_attr['word'])

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    not currently_playing(input) and
                    is_intent_name("AMAZON.NoIntent")(input))
def no_handler(handler_input):
    """Handler for No Intent, only if the player said no for
    a new game.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    session_attr['game_state'] = "ENDED"
    session_attr['ended_session_count'] += 1

    handler_input.attributes_manager.persistent_attributes = session_attr
    handler_input.attributes_manager.save_persistent_attributes()

    speech_text = "Ok. See you next time!!"

    handler_input.response_builder.speak(speech_text)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("AMAZON.FallbackIntent")(input) or
                    is_intent_name("AMAZON.YesIntent")(input) or
                    is_intent_name("AMAZON.NoIntent")(input))
def fallback_handler(handler_input):
    """AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes

    if ("game_state" in session_attr and
            session_attr["game_state"] == "STARTED"):
        speech_text = (
            "The {} skill can't help you with that.  "
            "Try asking for an example sentence. ".format(SKILL_NAME))
        reprompt = "Please try to spell {}".format(session_attr['word'])
    else:
        speech_text = (
            "The {} skill can't help you with that.  "
            "It will ask you to spell words and provide definitions and example sentences. "
            "Would you like to play?".format(SKILL_NAME))
        reprompt = "Say yes to start the game or no to quit."

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input: True)
def unhandled_intent_handler(handler_input):
    """Handler for all other unhandled requests."""
    # type: (HandlerInput) -> Response
    speech = "I can't handle that kind of input. Sorry."
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    # type: (HandlerInput, Exception) -> Response
    logger.error(exception, exc_info=True)
    speech = "Sorry, I can't understand that. Please say again!!"
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.global_response_interceptor()
def log_response(handler_input, response):
    """Response logger."""
    # type: (HandlerInput, Response) -> None
    logger.info("Response: {}".format(response))


@sb.request_handler(can_handle_func=lambda input:
                    currently_playing(input) and
                    is_intent_name("DefineWordIntent")(input))
def define_word_handler(handler_input):
    """Handler for processing guess with target."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    word = session_attr["word"]
    try:
        word_definition = session_attr['defs'][word]
    except KeyError:
        session_attr['defs'][word] = get_word_details(word)
        word_definition = session_attr['defs'][word]

    secure_random = random.SystemRandom()
    speech_text = ("Here's a definition for {word}. {defi}".
                   format(word=word, defi=secure_random.choice(word_definition['def'])))
    reprompt = ("Here's a definition for {word}. {defi}".
                format(word=word, defi=secure_random.choice(word_definition['def'])))

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    currently_playing(input) and
                    is_intent_name("SentenceIntent")(input))
def sentence_request_handler(handler_input):
    """Handler for processing guess with target."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    word = session_attr["word"]
    try:
        word_definition = session_attr['defs'][word]
    except KeyError:
        session_attr['defs'][word] = get_word_details(word)
        word_definition = session_attr['defs'][word]

    secure_random = random.SystemRandom()
    speech_text = ("Here's an example sentence for {word}. {sent}".
                   format(word=word, sent=secure_random.choice(word_definition['sent'])))
    reprompt = ("Here's an example sentence for {word}. {sent}".
                format(word=word, sent=secure_random.choice(word_definition['sent'])))

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    currently_playing(input) and
                    is_intent_name("SpellWordIntent")(input))
def sentence_request_handler(handler_input):
    """Handler for processing guess with target."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    word = session_attr["word"]
    spelling = '. '.join(list(word))
    attempt = ''.join(handler_input.request_envelope.request.intent.slots["spelling"].value)

    if word != attempt:
        speech_text = (
            "Sorry, but your spelling was incorrect. The correct spelling is. {}".format(spelling)
        )
        reprompt = "Say yes to start get a new word or no to end the game"
        session_attr["games_played"] += 1
        session_attr["game_state"] = "ENDED"

        handler_input.attributes_manager.persistent_attributes = session_attr
        handler_input.attributes_manager.save_persistent_attributes()
    elif word == attempt:
        speech_text = (
            "Congratulations. You spelled {} correctly!"
            "Would you like to play a new game?".format(word)
        )
        reprompt = "Say yes to start get a new word or no to end the game"
        session_attr["games_played"] += 1
        session_attr["game_state"] = "ENDED"

        handler_input.attributes_manager.persistent_attributes = session_attr
        handler_input.attributes_manager.save_persistent_attributes()
    else:
        speech_text = "Sorry, I didn't get that. Try spelling the word again."
        reprompt = "Try spelling the word again."

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


def currently_playing(handler_input):
    """Function that acts as can handle for game state."""
    # type: (HandlerInput) -> bool
    is_currently_playing = False
    session_attr = handler_input.attributes_manager.session_attributes

    if ("game_state" in session_attr
            and session_attr['game_state'] == "STARTED"):
        is_currently_playing = True

    return is_currently_playing


def get_word_details(word):
    durl = "https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={key}"
    durl = durl.format(word=word, key=os.environ['dict_key'])
    results = requests.get(durl)
    content = json.loads(results.content)
    definition = [a.split(" : ")[0] for a in content[0]['shortdef']]
    exsentence = ['there are no valid example sentences to use']
    for d in content[0]['def'][0]['sseq']:
        defs = [a[1] for a in d[0][1]['dt'] if a[0] == 'vis'][0]
        exsentence.append([d['t'] for d in defs][0])
    exsentence = [re.sub('{.*?}', '', a) for a in exsentence if re.search('}'+word+'{', a)]
    return {"def": definition, "sent": exsentence}


lambda_handler = sb.lambda_handler()
