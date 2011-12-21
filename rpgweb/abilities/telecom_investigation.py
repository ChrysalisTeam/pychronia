# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *

            elif name == "corrupted_chunks_lengths":
                assert len(value) == 2 and (value[0] <= value[1])
                assert isinstance(value[0], (int, long))
                assert isinstance(value[1], (int, long))



###corrupted_chunks_lengths

@staticmethod
def _corrupt_text_parts(text, corrupted_chunks_lengths, key_phrase=""):
    # Words of "key_phrase" will NECESSARILY be found in final corrupted message, if they exist in original message

    keywords = key_phrase.lower().split()
    words = text.split()

    result = []
    must_add = True

    while words:
        length = random.randint(corrupted_chunks_lengths[0], corrupted_chunks_lengths[1])
        selected_words = words[0:length]
        selected_words_lower = " ".join(selected_words).lower() # string, to avoid problems with punctuation marks
        words = words[length:]

        for key in keywords:
            if key in selected_words_lower:
                must_add = True
                break

        if must_add:
            result += selected_words
        else:
            result += ["..."]
        must_add = not must_add

    return " ".join(result)

@readonly_method
def _get_corrupted_introduction(self, target_username, key_phrase):
    # Words of "key_phrase" will NECESSARILY be found in final corrupted message, if they exist in original message

    from django.utils.html import strip_tags

    chunk_lengths = self.get_global_parameter("corrupted_chunks_lengths")
    result = "\n"

    raw_team_intro = self.get_game_instructions(target_username)["team_introduction"]
    if raw_team_intro:
        team_introductions = raw_team_intro.split(
            "<hr/>") # some teams like achariths have several parts in their intro
        intro_chunks = [self._corrupt_text_parts(strip_tags(intro), chunk_lengths, key_phrase) for intro in
                        team_introductions]
        result += "\n\n------------\n\n".join(intro_chunks)

    instructions = [msg for msg in self.get_all_sent_messages() if msg["id"] == "instructions_" + target_username]
    if instructions:
        if raw_team_intro:
            result += "\n\n------------\n\n"
        instruction = instructions[0]
        result += "**" + _("Message") + "**" + "\n\n" + _("From: ") + instruction["sender_email"] + "\n\n" + _(
            "To: ") + str(instruction["recipient_emails"]) +\
                  "\n\n" + _("Subject: ") + instruction["subject"] + "\n\n"
        result += "\n" + self._corrupt_text_parts(instruction["body"], chunk_lengths, key_phrase)
    else:
        logging.error("Player instructions message for %s not found !" % target_username, exc_info=True)

    return result


@transaction_watcher
def launch_telecom_investigation(self, username, target_username):
    if self.get_global_parameter("telecom_investigations_done") >= self.get_global_parameter(
        "max_telecom_investigations"):
        raise UsageError(
            _("Teleporters have exhausted all their energy, no more operations possible before two days."))

    target_official_name = self.get_official_name_from_username(target_username)

    if target_username == username:
        raise UsageError(_("Opening an inquiry into yourself doesn't make much sense."))

    remote_email = "investigator@special.com" # dummy domain too
    local_email = self.get_character_email(username)


    # request email to allow interception

    subject = _("Investigation Request for character %(target_official_name)s") %\
              SDICT(target_official_name=target_official_name)
    body = _("Please let me know anything you may discover about this individual.")
    self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=True)


    # answer email

    subject = _('<Inquiry Results for %(target_official_name)s>') %\
              SDICT(target_official_name=target_official_name)

    body = self._get_corrupted_introduction(target_username, target_official_name)

    attachment = None

    msg_id = self.post_message(remote_email, local_email, subject, body, attachment,
                               date_or_delay_mn=self.get_global_parameter("telecom_investigation_delays"))

    self.data["global_parameters"]["telecom_investigations_done"] += 1 # IMPORTANT

    self.log_game_event(_noop('Character inquiry opened by %(username)s into %(target_official_name)s'),
                         PersistentDict(username=username, target_official_name=target_official_name),
                         url=self.get_message_viewer_url(msg_id))
