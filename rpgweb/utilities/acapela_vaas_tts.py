# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import requests, urlparse


class AcapelaClient(object):


    def __init__(self, url, login, password, application, environment):

        assert environment.upper() == environment and " " not in environment

        self._url = url

        self.connection_fields = dict(prot_vers="2",
                                      cl_env=environment,
                                      cl_vers="1-0",
                                      cl_login=login,
                                      cl_app=application,
                                      cl_pwd=password,)


    def _process_api_call(self, **kwargs):
        """
        Returns a dict of sample information, or binary data, depending on response_type argument.
        
        Raises EnvironmentError if problems.
        """

        final_params = self.connection_fields.copy()

        for key, value in kwargs.items():
            if value is not None:
                final_params[self.ARGUMENT_MAPPER[key]] = value
        del kwargs, key, value

        print("INPUT", final_params)

        res = requests.post(self._url, data=final_params)
        res.raise_for_status()


        if final_params.get("response_type") not in (None, "INFO"):
            return res.content # binary audio data
        else:

            raw = res.text

            print("RAW", raw) # ex: raw = "w=&snd_time=1892.75&get_count=0&snd_id=221335548_cba848475cb40&asw_pos_init_offset=0&asw_pos_text_offset=0&snd_url=http://vaas.acapela-group.com/MESSAGES/009086065076095086065065083/EVAL_4775608/sounds/221335548_cba848475cb40.mp3&snd_size=13279&res=OK&create_echo="

            values = dict(urlparse.parse_qsl(raw, keep_blank_values=True, strict_parsing=__debug__))

            if values["res"] != "OK":
                klass = EnvironmentError # at the moment, no need to distinguish errors...
                msg = "VAAS %s: %s" % (values["err_code"], values["err_msg"])
                raise klass(msg)

            res = dict(sound_id=values["snd_id"],
                        sound_url=values["snd_url"],
                        sound_size=values["snd_size"], # in bytes

                        alt_sound_url=values.get("alt_snd_url"),
                        alt_sound_size=values.get("alt_snd_size"),

                        sound_time=values["snd_time"], # in milliseconds
                        get_count=int(values["get_count"]), # how many [GET] requests where done for that sample
                        warning=values["w"],
                        # ignore asw_pos_init_offset and asw_pos_text_offset and create_echo ATM
                        )
            print("RESPONSE", res)
            return res


    def create_sample(self,
                        voice,
                        text,

                        comment=None, # the information to store concerning this operation (author, reason, ...) you can get it back 
                        response_type=None, # INFO(default, urlencoded params)/SOUND/STREAM

                        sound_id=None, # you can enforce the id to use/replace for a new message (do not use the dot character (\'.\') inside and make sure it is unique!).
                        volume=None, # min = 50, default = 32768, max = 65535 
                        speed=None, # min = 60, default = 180, max = 360 
                        shaping=None, # min = 50, default = 100, max = 150 

                        # for each equalizer value, min = -100, default = 0, max = 100 - for frequences 275Hz, 2.2kHz, 5kHz and 8.3kHz, respectively
                        equalizer1=None,
                        equalizer2=None,
                        equalizer3=None,
                        equalizer4=None,

                        format=None, # MP3/WAV/RAW - MP3 is assumed if ommited.
                        extension=None, # e.g.: ".mp3", ".wav", ...
                        mp3_compression=None, # Specify to select a custom compression format Variable Bit Rate (5 = max quality, 9 = min) or Constant Bit Rate (8 to 48 kbps) => VBR_X or CBR_X

                        alt_format=None, # You can associate two different types such as MP3 and WAV or RAW (but not WAV and RAW, use two requests for this).
                        alt_extension=None, # e.g.: ".mp3", ".wav", ...
                        alt_mp3_compression=None, # idem mp3_compression

                        # Set these to "ON" to receive word/bookmark/mouth positions file URL.
                        words=None,
                        bookmarks=None,
                        mouth=None,

                        request_start_time=None, # the start time (timestamp integer) of the request will be used to calculate the deadline for request treatment
                        timeout_value=None, # The time allocated to request treatment in seconds

                        # when choosing SOUND or STREAM response type
                        retrieve_alternate_sound=None, # Set to "yes" if you wish to receive the alternative file as response.
                        errors_in_id3_tags=None, # Set to "yes" if you wish to receive errors this way whenever possible instead of returning an internal server error (500)

                        # when choosing INFO response type 
                        request_echo=None, # ON to receive some of the message creation request fields in the response
                        redirection_url=None, # the url that the TTS server should POST-query with INFO params, to get a processed HTML result for the TTS request
                        ):

        params = locals().copy()
        del params["self"]
        return self._process_api_call(request_type="NEW", **params)


    def retrieve_sample(self,
                        sound_id,
                        message_location=None, # Specify to precise the location of the message targetted by this command - "CT_BUG_NOTIF" on a mispronunced message, "CONTENT_NOTIF" on a message notified for an inappropriate/illegal content or "MISC_BUG_NOTIF" on a message notified for another type of issue.

                        response_type=None,

                        request_start_time=None,
                        timeout_value=None,

                        retrieve_alternate_sound=None,
                        errors_in_id3_tags=None,

                        request_echo=None,
                        redirection_url=None,
                        ):

        params = locals().copy()
        del params["self"]
        return self._process_api_call(request_type="GET", **params)



    ARGUMENT_MAPPER = dict(
                           request_type="req_type",

                            voice="req_voice",
                            text="req_text",

                            comment="req_comment",
                            response_type="req_asw_type",

                            sound_id="req_snd_id",
                            message_location="req_loc",

                            volume="req_vol",
                            speed="req_spd",
                            shaping="req_vct",

                            equalizer1="req_eq1",
                            equalizer2="req_eq2",
                            equalizer3="req_eq3",
                            equalizer4="req_eq4",

                            format="req_snd_type",
                            extension="req_snd_ext",
                            mp3_compression="req_snd_kbps",

                            alt_format="req_alt_snd_type",
                            alt_extension="req_alt_snd_ext",
                            alt_mp3_compression="req_alt_snd_kbps",

                            words="req_wp",
                            bookmarks="req_bp",
                            mouth="req_mp",

                            request_start_time="req_start_time",
                            timeout_value="req_timeout",

                            retrieve_alternate_sound="req_asw_as_alt_snd",
                            errors_in_id3_tags="req_err_as_id3",

                            request_echo="req_echo",
                            redirection_url="req_asw_redirect_url",
                            )






VOICES_CONFS = (
    ("ar_SA", "Arabic (Saudi Arabia)", "Leila", "HQ", "F", "leila22k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Leila", "HQ", "F", "leila8k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Leila", "HQ", "F", "leila8ka"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Leila", "HQ", "F", "leila8kmu"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Mehdi", "HQ", "M", "mehdi22k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Mehdi", "HQ", "M", "mehdi8k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Mehdi", "HQ", "M", "mehdi8ka"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Mehdi", "HQ", "M", "mehdi8kmu"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Nizar", "HQ", "M", "nizar22k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Nizar", "HQ", "M", "nizar8k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Nizar", "HQ", "M", "nizar8ka"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Nizar", "HQ", "M", "nizar8kmu"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Salma", "HQ", "F", "salma22k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Salma", "HQ", "F", "salma8k"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Salma", "HQ", "F", "salma8ka"),
    ("ar_SA", "Arabic (Saudi Arabia)", "Salma", "HQ", "F", "salma8kmu"),
    ("ca_ES", "Catalan (Spain)", "Laia", "HQ", "F", "laia22k"),
    ("ca_ES", "Catalan (Spain)", "Laia", "HQ", "F", "laia8k"),
    ("ca_ES", "Catalan (Spain)", "Laia", "HQ", "F", "laia8ka"),
    ("ca_ES", "Catalan (Spain)", "Laia", "HQ", "F", "laia8kmu"),
    ("cs_CZ", "Czech", "Eliska", "HQ", "F", "eliska22k"),
    ("cs_CZ", "Czech", "Eliska", "HQ", "F", "eliska8k"),
    ("cs_CZ", "Czech", "Eliska", "HQ", "F", "eliska8ka"),
    ("cs_CZ", "Czech", "Eliska", "HQ", "F", "eliska8kmu"),
    ("da_DK", "Danish", "Mette", "HQ", "F", "mette22k"),
    ("da_DK", "Danish", "Mette", "HQ", "F", "mette8k"),
    ("da_DK", "Danish", "Mette", "HQ", "F", "mette8ka"),
    ("da_DK", "Danish", "Mette", "HQ", "F", "mette8kmu"),
    ("da_DK", "Danish", "Rasmus", "HQ", "M", "rasmus22k"),
    ("da_DK", "Danish", "Rasmus", "HQ", "M", "rasmus8k"),
    ("da_DK", "Danish", "Rasmus", "HQ", "M", "rasmus8ka"),
    ("da_DK", "Danish", "Rasmus", "HQ", "M", "rasmus8kmu"),
    ("nl_BE", "Dutch (Belgium)", "Jeroen", "HQ", "M", "jeroen22k"),
    ("nl_BE", "Dutch (Belgium)", "Jeroen", "HQ", "M", "jeroen8k"),
    ("nl_BE", "Dutch (Belgium)", "Jeroen", "HQ", "M", "jeroen8ka"),
    ("nl_BE", "Dutch (Belgium)", "Jeroen", "HQ", "M", "jeroen8kmu"),
    ("nl_BE", "Dutch (Belgium)", "Sofie", "HQ", "F", "sofie22k"),
    ("nl_BE", "Dutch (Belgium)", "Sofie", "HQ", "F", "sofie8k"),
    ("nl_BE", "Dutch (Belgium)", "Sofie", "HQ", "F", "sofie8ka"),
    ("nl_BE", "Dutch (Belgium)", "Sofie", "HQ", "F", "sofie8kmu"),
    ("nl_BE", "Dutch (Belgium)", "Zoe", "HQ", "F", "zoe22k"),
    ("nl_BE", "Dutch (Belgium)", "Zoe", "HQ", "F", "zoe8k"),
    ("nl_BE", "Dutch (Belgium)", "Zoe", "HQ", "F", "zoe8ka"),
    ("nl_BE", "Dutch (Belgium)", "Zoe", "HQ", "F", "zoe8kmu"),
    ("nl_NL", "Dutch (Netherlands)", "Daan", "HQ", "M", "daan22k"),
    ("nl_NL", "Dutch (Netherlands)", "Daan", "HQ", "M", "daan8k"),
    ("nl_NL", "Dutch (Netherlands)", "Daan", "HQ", "M", "daan8ka"),
    ("nl_NL", "Dutch (Netherlands)", "Daan", "HQ", "M", "daan8kmu"),
    ("nl_NL", "Dutch (Netherlands)", "Femke", "HQ", "F", "femke22k"),
    ("nl_NL", "Dutch (Netherlands)", "Femke", "HQ", "F", "femke8k"),
    ("nl_NL", "Dutch (Netherlands)", "Femke", "HQ", "F", "femke8ka"),
    ("nl_NL", "Dutch (Netherlands)", "Femke", "HQ", "F", "femke8kmu"),
    ("nl_NL", "Dutch (Netherlands)", "Jasmijn", "HQ", "F", "jasmijn22k"),
    ("nl_NL", "Dutch (Netherlands)", "Jasmijn", "HQ", "F", "jasmijn8k"),
    ("nl_NL", "Dutch (Netherlands)", "Jasmijn", "HQ", "F", "jasmijn8ka"),
    ("nl_NL", "Dutch (Netherlands)", "Jasmijn", "HQ", "F", "jasmijn8kmu"),
    ("nl_NL", "Dutch (Netherlands)", "Max", "HQ", "M", "max22k"),
    ("nl_NL", "Dutch (Netherlands)", "Max", "HQ", "M", "max8k"),
    ("nl_NL", "Dutch (Netherlands)", "Max", "HQ", "M", "max8ka"),
    ("nl_NL", "Dutch (Netherlands)", "Max", "HQ", "M", "max8kmu"),
    ("en_IN", "English (India)", "Deepa", "HQ", "F", "deepa22k"),
    ("en_IN", "English (India)", "Deepa", "HQ", "F", "deepa8k"),
    ("en_IN", "English (India)", "Deepa", "HQ", "F", "deepa8ka"),
    ("en_IN", "English (India)", "Deepa", "HQ", "F", "deepa8kmu"),
    ("en_GB", "English (UK)", "Graham", "HQ", "M", "graham22k"),
    ("en_GB", "English (UK)", "Graham", "HQ", "M", "graham8k"),
    ("en_GB", "English (UK)", "Graham", "HQ", "M", "graham8ka"),
    ("en_GB", "English (UK)", "Graham", "HQ", "M", "graham8kmu"),
    ("en_GB", "English (UK)", "Lucy", "HQ", "F", "lucy22k"),
    ("en_GB", "English (UK)", "Lucy", "HQ", "F", "lucy8k"),
    ("en_GB", "English (UK)", "Lucy", "HQ", "F", "lucy8ka"),
    ("en_GB", "English (UK)", "Lucy", "HQ", "F", "lucy8kmu"),
    ("en_GB", "English (UK)", "Nizareng", "HQ", "M", "nizareng22k"),
    ("en_GB", "English (UK)", "Nizareng", "HQ", "M", "nizareng8k"),
    ("en_GB", "English (UK)", "Nizareng", "HQ", "M", "nizareng8ka"),
    ("en_GB", "English (UK)", "Nizareng", "HQ", "M", "nizareng8kmu"),
    ("en_GB", "English (UK)", "Peter", "HQ", "M", "peter22k"),
    ("en_GB", "English (UK)", "Peter", "HQ", "M", "peter8k"),
    ("en_GB", "English (UK)", "Peter", "HQ", "M", "peter8ka"),
    ("en_GB", "English (UK)", "Peter", "HQ", "M", "peter8kmu"),
    ("en_GB", "English (UK)", "QueenElizabeth", "HQ", "F", "queenelizabeth22k"),
    ("en_GB", "English (UK)", "QueenElizabeth", "HQ", "F", "queenelizabeth8k"),
    ("en_GB", "English (UK)", "QueenElizabeth", "HQ", "F", "queenelizabeth8ka"),
    ("en_GB", "English (UK)", "QueenElizabeth", "HQ", "F", "queenelizabeth8kmu"),
    ("en_GB", "English (UK)", "Rachel", "HQ", "F", "rachel22k"),
    ("en_GB", "English (UK)", "Rachel", "HQ", "F", "rachel8k"),
    ("en_GB", "English (UK)", "Rachel", "HQ", "F", "rachel8ka"),
    ("en_GB", "English (UK)", "Rachel", "HQ", "F", "rachel8kmu"),
    ("en_US", "English (USA)", "Heather", "HQ", "F", "heather22k"),
    ("en_US", "English (USA)", "Heather", "HQ", "F", "heather8k"),
    ("en_US", "English (USA)", "Heather", "HQ", "F", "heather8ka"),
    ("en_US", "English (USA)", "Heather", "HQ", "F", "heather8kmu"),
    ("en_US", "English (USA)", "Kenny", "HQ", "M", "kenny22k"),
    ("en_US", "English (USA)", "Kenny", "HQ", "M", "kenny8k"),
    ("en_US", "English (USA)", "Kenny", "HQ", "M", "kenny8ka"),
    ("en_US", "English (USA)", "Kenny", "HQ", "M", "kenny8kmu"),
    ("en_US", "English (USA)", "Laura", "HQ", "F", "laura22k"),
    ("en_US", "English (USA)", "Laura", "HQ", "F", "laura8k"),
    ("en_US", "English (USA)", "Laura", "HQ", "F", "laura8ka"),
    ("en_US", "English (USA)", "Laura", "HQ", "F", "laura8kmu"),
    ("en_US", "English (USA)", "Micah", "HQ", "M", "micah22k"),
    ("en_US", "English (USA)", "Micah", "HQ", "M", "micah8k"),
    ("en_US", "English (USA)", "Micah", "HQ", "M", "micah8ka"),
    ("en_US", "English (USA)", "Micah", "HQ", "M", "micah8kmu"),
    ("en_US", "English (USA)", "Nelly", "HQ", "F", "nelly22k"),
    ("en_US", "English (USA)", "Nelly", "HQ", "F", "nelly8k"),
    ("en_US", "English (USA)", "Nelly", "HQ", "F", "nelly8ka"),
    ("en_US", "English (USA)", "Nelly", "HQ", "F", "nelly8kmu"),
    ("en_US", "English (USA)", "Ryan", "HQ", "M", "ryan22k"),
    ("en_US", "English (USA)", "Ryan", "HQ", "M", "ryan8k"),
    ("en_US", "English (USA)", "Ryan", "HQ", "M", "ryan8ka"),
    ("en_US", "English (USA)", "Ryan", "HQ", "M", "ryan8kmu"),
    ("en_US", "English (USA)", "Saul", "HQ", "M", "saul22k"),
    ("en_US", "English (USA)", "Saul", "HQ", "M", "saul8ka"),
    ("en_US", "English (USA)", "Saul", "HQ", "M", "saul8kmu"),
    ("en_US", "English (USA)", "Tracy", "HQ", "F", "tracy22k"),
    ("en_US", "English (USA)", "Tracy", "HQ", "F", "tracy8k"),
    ("en_US", "English (USA)", "Tracy", "HQ", "F", "tracy8ka"),
    ("en_US", "English (USA)", "Tracy", "HQ", "F", "tracy8kmu"),
    ("fi_FI", "Finnish", "Sanna", "HQ", "F", "sanna22k"),
    ("fi_FI", "Finnish", "Sanna", "HQ", "F", "sanna8k"),
    ("fi_FI", "Finnish", "Sanna", "HQ", "F", "sanna8ka"),
    ("fi_FI", "Finnish", "Sanna", "HQ", "F", "sanna8kmu"),
    ("fr_BE", "French (Belgium)", "Justine", "HQ", "F", "justine22k"),
    ("fr_BE", "French (Belgium)", "Justine", "HQ", "F", "justine8k"),
    ("fr_BE", "French (Belgium)", "Justine", "HQ", "F", "justine8ka"),
    ("fr_BE", "French (Belgium)", "Justine", "HQ", "F", "justine8kmu"),
    ("fr_CA", "French (Canada)", "Louise", "HQ", "F", "louise22k"),
    ("fr_CA", "French (Canada)", "Louise", "HQ", "F", "louise8k"),
    ("fr_CA", "French (Canada)", "Louise", "HQ", "F", "louise8ka"),
    ("fr_CA", "French (Canada)", "Louise", "HQ", "F", "louise8kmu"),
    ("fr_FR", "French (France)", "Alice", "HQ", "F", "alice22k"),
    ("fr_FR", "French (France)", "Alice", "HQ", "F", "alice8k"),
    ("fr_FR", "French (France)", "Alice", "HQ", "F", "alice8ka"),
    ("fr_FR", "French (France)", "Alice", "HQ", "F", "alice8kmu"),
    ("fr_FR", "French (France)", "Antoine", "HQ", "M", "antoine22k"),
    ("fr_FR", "French (France)", "Antoine", "HQ", "M", "antoine8k"),
    ("fr_FR", "French (France)", "Antoine", "HQ", "M", "antoine8ka"),
    ("fr_FR", "French (France)", "Antoine", "HQ", "M", "antoine8kmu"),
    ("fr_FR", "French (France)", "Bruno", "HQ", "M", "bruno22k"),
    ("fr_FR", "French (France)", "Bruno", "HQ", "M", "bruno8k"),
    ("fr_FR", "French (France)", "Bruno", "HQ", "M", "bruno8ka"),
    ("fr_FR", "French (France)", "Bruno", "HQ", "M", "bruno8kmu"),
    ("fr_FR", "French (France)", "Claire", "HQ", "F", "claire22k"),
    ("fr_FR", "French (France)", "Claire", "HQ", "F", "claire8k"),
    ("fr_FR", "French (France)", "Claire", "HQ", "F", "claire8ka"),
    ("fr_FR", "French (France)", "Claire", "HQ", "F", "claire8kmu"),
    ("fr_FR", "French (France)", "Julie", "HQ", "F", "julie22k"),
    ("fr_FR", "French (France)", "Julie", "HQ", "F", "julie8k"),
    ("fr_FR", "French (France)", "Julie", "HQ", "F", "julie8ka"),
    ("fr_FR", "French (France)", "Julie", "HQ", "F", "julie8kmu"),
    ("fr_FR", "French (France)", "Margaux", "HQ", "F", "margaux22k"),
    ("fr_FR", "French (France)", "Margaux", "HQ", "F", "margaux8k"),
    ("fr_FR", "French (France)", "Margaux", "HQ", "F", "margaux8ka"),
    ("fr_FR", "French (France)", "Margaux", "HQ", "F", "margaux8kmu"),
    ("fr_FR", "French (France)", "Robot", "HQ", "M", "robot22k"),
    ("de_DE", "German", "Andreas", "HQ", "M", "andreas22k"),
    ("de_DE", "German", "Andreas", "HQ", "M", "andreas8k"),
    ("de_DE", "German", "Andreas", "HQ", "M", "andreas8ka"),
    ("de_DE", "German", "Andreas", "HQ", "M", "andreas8kmu"),
    ("de_DE", "German", "Julia", "HQ", "F", "julia22k"),
    ("de_DE", "German", "Julia", "HQ", "F", "julia8k"),
    ("de_DE", "German", "Julia", "HQ", "F", "julia8ka"),
    ("de_DE", "German", "Julia", "HQ", "F", "julia8kmu"),
    ("de_DE", "German", "Klaus", "HQ", "M", "klaus22k"),
    ("de_DE", "German", "Klaus", "HQ", "M", "klaus8k"),
    ("de_DE", "German", "Klaus", "HQ", "M", "klaus8ka"),
    ("de_DE", "German", "Klaus", "HQ", "M", "klaus8kmu"),
    ("de_DE", "German", "Sarah", "HQ", "F", "sarah22k"),
    ("de_DE", "German", "Sarah", "HQ", "F", "sarah8k"),
    ("de_DE", "German", "Sarah", "HQ", "F", "sarah8ka"),
    ("de_DE", "German", "Sarah", "HQ", "F", "sarah8kmu"),
    ("el_GR", "Greek", "Dimitris", "HQ", "M", "dimitris22k"),
    ("el_GR", "Greek", "Dimitris", "HQ", "M", "dimitris8k"),
    ("el_GR", "Greek", "Dimitris", "HQ", "M", "dimitris8ka"),
    ("el_GR", "Greek", "Dimitris", "HQ", "M", "dimitris8kmu"),
    ("it_IT", "Italian", "Chiara", "HQ", "F", "chiara8k"),
    ("it_IT", "Italian", "Chiara", "HQ", "F", "chiara8ka"),
    ("it_IT", "Italian", "Chiara", "HQ", "F", "chiara8kmu"),
    ("it_IT", "Italian", "Fabiana", "HQ", "F", "fabiana8k"),
    ("it_IT", "Italian", "Fabiana", "HQ", "F", "fabiana8ka"),
    ("it_IT", "Italian", "Fabiana", "HQ", "F", "fabiana8kmu"),
    ("it_IT", "Italian", "Vittorio", "HQ", "M", "vittorio8k"),
    ("it_IT", "Italian", "Vittorio", "HQ", "M", "vittorio8ka"),
    ("it_IT", "Italian", "Vittorio", "HQ", "M", "vittorio8kmu"),
    ("it_IT", "Italian", "chiara", "HQ", "F", "chiara22k"),
    ("it_IT", "Italian", "fabiana", "HQ", "F", "fabiana22k"),
    ("it_IT", "Italian", "vittorio", "HQ", "M", "vittorio22k"),
    ("no_NO", "Norwegian", "Bente", "HQ", "F", "bente22k"),
    ("no_NO", "Norwegian", "Bente", "HQ", "F", "bente8k"),
    ("no_NO", "Norwegian", "Bente", "HQ", "F", "bente8ka"),
    ("no_NO", "Norwegian", "Bente", "HQ", "F", "bente8kmu"),
    ("no_NO", "Norwegian", "Kari", "HQ", "F", "kari22k"),
    ("no_NO", "Norwegian", "Kari", "HQ", "F", "kari8k"),
    ("no_NO", "Norwegian", "Kari", "HQ", "F", "kari8ka"),
    ("no_NO", "Norwegian", "Kari", "HQ", "F", "kari8kmu"),
    ("no_NO", "Norwegian", "Olav", "HQ", "M", "olav22k"),
    ("no_NO", "Norwegian", "Olav", "HQ", "M", "olav8k"),
    ("no_NO", "Norwegian", "Olav", "HQ", "M", "olav8ka"),
    ("no_NO", "Norwegian", "Olav", "HQ", "M", "olav8kmu"),
    ("pl_PL", "Polish", "Ania", "HQ", "F", "ania22k"),
    ("pl_PL", "Polish", "Ania", "HQ", "F", "ania8k"),
    ("pl_PL", "Polish", "Ania", "HQ", "F", "ania8ka"),
    ("pl_PL", "Polish", "Ania", "HQ", "F", "ania8kmu"),
    ("pt_BR", "Portuguese (Brazil)", "Marcia", "HQ", "F", "marcia22k"),
    ("pt_BR", "Portuguese (Brazil)", "Marcia", "HQ", "F", "marcia8k"),
    ("pt_BR", "Portuguese (Brazil)", "Marcia", "HQ", "F", "marcia8ka"),
    ("pt_BR", "Portuguese (Brazil)", "Marcia", "HQ", "F", "marcia8kmu"),
    ("pt_PT", "Portuguese (Portugal)", "Celia", "HQ", "F", "celia22k"),
    ("pt_PT", "Portuguese (Portugal)", "Celia", "HQ", "F", "celia8k"),
    ("pt_PT", "Portuguese (Portugal)", "Celia", "HQ", "F", "celia8ka"),
    ("pt_PT", "Portuguese (Portugal)", "Celia", "HQ", "F", "celia8kmu"),
    ("ru_RU", "Russian", "Alyona", "HQ", "F", "alyona22k"),
    ("ru_RU", "Russian", "Alyona", "HQ", "F", "alyona8k"),
    ("ru_RU", "Russian", "Alyona", "HQ", "F", "alyona8ka"),
    ("ru_RU", "Russian", "Alyona", "HQ", "F", "alyona8kmu"),
    ("sc_SE", "Scanian (Sweden)", "Mia", "HQ", "F", "mia22k"),
    ("sc_SE", "Scanian (Sweden)", "Mia", "HQ", "F", "mia8k"),
    ("sc_SE", "Scanian (Sweden)", "Mia", "HQ", "F", "mia8ka"),
    ("sc_SE", "Scanian (Sweden)", "Mia", "HQ", "F", "mia8kmu"),
    ("es_ES", "Spanish (Spain)", "Antonio", "HQ", "M", "antonio22k"),
    ("es_ES", "Spanish (Spain)", "Antonio", "HQ", "M", "antonio8k"),
    ("es_ES", "Spanish (Spain)", "Antonio", "HQ", "M", "antonio8ka"),
    ("es_ES", "Spanish (Spain)", "Antonio", "HQ", "M", "antonio8kmu"),
    ("es_ES", "Spanish (Spain)", "Ines", "HQ", "F", "ines22k"),
    ("es_ES", "Spanish (Spain)", "Ines", "HQ", "F", "ines8k"),
    ("es_ES", "Spanish (Spain)", "Ines", "HQ", "F", "ines8ka"),
    ("es_ES", "Spanish (Spain)", "Ines", "HQ", "F", "ines8kmu"),
    ("es_ES", "Spanish (Spain)", "Maria", "HQ", "F", "maria22k"),
    ("es_ES", "Spanish (Spain)", "Maria", "HQ", "F", "maria8k"),
    ("es_ES", "Spanish (Spain)", "Maria", "HQ", "F", "maria8ka"),
    ("es_ES", "Spanish (Spain)", "Maria", "HQ", "F", "maria8kmu"),
    ("es_US", "Spanish (USA)", "Rosa", "HQ", "F", "rosa22k"),
    ("es_US", "Spanish (USA)", "Rosa", "HQ", "F", "rosa8k"),
    ("es_US", "Spanish (USA)", "Rosa", "HQ", "F", "rosa8ka"),
    ("es_US", "Spanish (USA)", "Rosa", "HQ", "F", "rosa8kmu"),
    ("sv_SE", "Swedish", "Elin", "HQ", "F", "elin22k"),
    ("sv_SE", "Swedish", "Elin", "HQ", "F", "elin8k"),
    ("sv_SE", "Swedish", "Elin", "HQ", "F", "elin8ka"),
    ("sv_SE", "Swedish", "Elin", "HQ", "F", "elin8kmu"),
    ("sv_SE", "Swedish", "Emil", "HQ", "M", "emil22k"),
    ("sv_SE", "Swedish", "Emil", "HQ", "M", "emil8k"),
    ("sv_SE", "Swedish", "Emil", "HQ", "M", "emil8ka"),
    ("sv_SE", "Swedish", "Emil", "HQ", "M", "emil8kmu"),
    ("sv_SE", "Swedish", "Emma", "HQ", "F", "emma22k"),
    ("sv_SE", "Swedish", "Emma", "HQ", "F", "emma8k"),
    ("sv_SE", "Swedish", "Emma", "HQ", "F", "emma8ka"),
    ("sv_SE", "Swedish", "Emma", "HQ", "F", "emma8kmu"),
    ("sv_SE", "Swedish", "Erik", "HQ", "M", "erik22k"),
    ("sv_SE", "Swedish", "Erik", "HQ", "M", "erik8k"),
    ("sv_SE", "Swedish", "Erik", "HQ", "M", "erik8ka"),
    ("sv_SE", "Swedish", "Erik", "HQ", "M", "erik8kmu"),
    ("sv_FI", "Swedish (Finland)", "Samuel", "HQ", "M", "samuel22k"),
    ("sv_FI", "Swedish (Finland)", "Samuel", "HQ", "M", "samuel8k"),
    ("sv_FI", "Swedish (Finland)", "Samuel", "HQ", "M", "samuel8ka"),
    ("sv_FI", "Swedish (Finland)", "Samuel", "HQ", "M", "samuel8kmu"),
    ("gb_SE", "Swedish - Gothenburg (Sweden)", "Kal", "HQ", "M", "kal22k"),
    ("gb_SE", "Swedish - Gothenburg (Sweden)", "Kal", "HQ", "M", "kal8k"),
    ("gb_SE", "Swedish - Gothenburg (Sweden)", "Kal", "HQ", "M", "kal8ka"),
    ("gb_SE", "Swedish - Gothenburg (Sweden)", "Kal", "HQ", "M", "kal8kmu"),
    ("tr_TR", "Turkish", "Ipek", "HQ", "F", "ipek22k"),
    ("tr_TR", "Turkish", "Ipek", "HQ", "F", "ipek8k"),
    ("tr_TR", "Turkish", "Ipek", "HQ", "F", "ipek8ka"),
    ("tr_TR", "Turkish", "Ipek", "HQ", "F", "ipek8kmu"),
)

AVAILABLE_VOICE_IDS = [voice[5] for voice in VOICES_CONFS]





if __name__ == "__main__":

    client = AcapelaClient(url="http://vaas.acapela-group.com/Services/Synthesizer",
                           login="EVAL_VAAS",
                           application="EVAL_4775608",
                           password="",
                           environment="PYTHON_2.7_WINDOWS_VISTA")

    client.create_sample(voice="ipek8k", text="1 2 3 4 5", response_type="SOUND")
    #client.retrieve_sample(sound_id="221335548_cba848475cb40")


""" hidden API, like DEL ??
    def notify_sample(self,
                        sound_id,
                        request_subtype, # Specify to precise the purpose of the request. You can use "CONTENT" for an inappropriate/illegal content, "CT_BUG" for a mispronunced message or "MISC_BUG" for another bug related to the message.
                      
                        response_type=None,
                      
                        message_location=None,
                        comment=None,

                        request_start_time=None, 
                        timeout_value=None, 

                        retrieve_alternate_sound=None,
                        errors_in_id3_tags=None, 
                        
                        request_echo=None,
                        ):
                                   
        params = locals().copy()
        del params["self"]
        
        self._process_api_call(request_type="GET", **params)       
"""
