# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *

from pychronia_game import views


class MenuEntry:

    def __init__(self, request, title=None, view=None, submenus=None, view_kwargs=None, forced_visibility=None):
        assert isinstance(title, unicode) or view
        assert view or submenus
        assert view or not view_kwargs
        assert forced_visibility is None or isinstance(forced_visibility, bool)

        self.title = title or view.relevant_title(request.datamanager)

        if view:
            view_kwargs = view_kwargs if view_kwargs else {}
            self.url = game_view_url(view, datamanager=request.datamanager, **view_kwargs)
        else:
            self.url = None

        self.submenus = tuple(submenu for submenu in submenus if submenu) if submenus else []
        self.user_access = view.get_access_token(request.datamanager) if view else None
        self.forced_visibility = forced_visibility
        self.is_active = bool(self.url and (self.user_access == AccessResult.available)) # doesn't rely on submenus state
        self.is_novelty = not view.has_user_accessed_view(request.datamanager) if view else False
        ##print(title, "view is marked as novelty", self.is_novelty)

    @property
    def is_visible(self):
        if self.forced_visibility is not None:
            return self.forced_visibility
        else:
            return bool(self.submenus or (self.user_access in (AccessResult.available, AccessResult.permission_required)))




def _generate_web_menu(request, menu_entry_generator):

    menu_entry = menu_entry_generator
    datamanager = request.datamanager
    user = datamanager.user

    # # Special additions to menu entries ##

    processed_view = getattr(request, "processed_view", None) # GameView instance set if said view was executed


    if user.is_authenticated and (not processed_view or processed_view.NAME != views.standard_conversations.NAME):
        unread_msgs_count = datamanager.get_unread_messages_count()
        standard_conversations_suffix = u"" ### TODO FIXME NBSP + u"(%d)" % unread_msgs_count
    else:
        standard_conversations_suffix = u""


    if user.is_authenticated and (not processed_view or processed_view.NAME != views.chatroom.NAME):
        # same for chatroom
        num_chatters = len(request.datamanager.get_chatting_users(exclude_current=True))
        chatroom_suffix = NBSP + u"(%d)" % num_chatters
    else:
        chatroom_suffix = u""


    full_menu_tree = menu_entry(_(u"Anthropia"), views.homepage,
        (
            # encoding note : \xa0 <-> &nbsp <-> alt+0160;

            menu_entry(_(u"Auction"), views.homepage,
                        (
                           ###menu_entry(_(u"Home"), views.homepage),
                           ###menu_entry(_(u"Opening"), views.opening),
                           ###menu_entry(_(u"Instructions"), views.instructions),
                           menu_entry(view=views.view_characters),
                           menu_entry(view=views.view_sales),
                           menu_entry(view=views.auction_items_slideshow),
                           menu_entry(_(u"Auction Chatroom") + chatroom_suffix, view=views.chatroom),
                           # menu_entry(_(u"Radio Messages"), views.personal_radio_messages_listing), # TODO INTEGRATE TO INFO PAGES ???
                       )),

            menu_entry(_(u"Media"), views.view_encyclopedia,
                       (
                         menu_entry(view=views.view_encyclopedia),

                         menu_entry(view=views.personal_webradio_page),
                         menu_entry(view=views.view_world_map),

                         # menu_entry(_(u"__EncryptedFolder__"), view=views.encrypted_folder, view_kwargs=dict(folder="guy2_report"), forced_visibility=(False if not user.is_master else None)), # TODO REMOVE ME
                         # menu_entry(_(u"__PublicWebradio__"), view=views.public_webradio, forced_visibility=(False if not user.is_master else None)), # TODO REMOVE ME

                      )),

            menu_entry(_(u"Messaging"), (views.all_dispatched_messages if user.is_master else views.standard_conversations),
                      (
                         menu_entry(view=views.all_dispatched_messages), # master only
                         menu_entry(view=views.all_queued_messages), # master only
                         menu_entry(_(u"My conversations") + standard_conversations_suffix, view=views.standard_conversations), # suffix is the count of unread MESSAGES
                         menu_entry(view=views.intercepted_messages),
                         menu_entry(view=views.all_archived_messages),
                         menu_entry(view=views.messages_templates), # master only
                         menu_entry(view=views.compose_message),
                      )),

            menu_entry(_(u"Abilities"), views.ability_introduction, # FIXME
                       (

                        menu_entry(view=views.mercenaries_hiring),
                        menu_entry(view=views.wiretapping_management),

                        menu_entry(view=views.house_locking),

                        menu_entry(view=views.runic_translation),
                        menu_entry(view=views.matter_analysis),
                        menu_entry(view=views.chess_challenge),
                        menu_entry(view=views.geoip_location),
                        menu_entry(view=views.world_scan),

                        menu_entry(view=views.artificial_intelligence),

                        menu_entry(view=views.business_escrow),
                        menu_entry(view=views.black_market),
                        menu_entry(view=views.telecom_investigation),

                        ##menu_entry(_(u"Telecom Investigation"), view=views.telecom_investigation),
                        # menu_entry(_(u"Agents Hiring"), view=views.network_management),
                        # menu_entry(_(u"Oracles"), view=views.contact_djinns),
                        # menu_entry(_(u"Mercenary Commandos"), view=views.mercenary_commandos),
                        # menu_entry(_(u"Teleportations"), view=views.teldorian_teleportations),
                        # menu_entry(_(u"Zealot Attacks"), view=views.akarith_attacks),
                        # menu_entry(_(u"Telecom Investigations"), view=views.telecom_investigation),
                        # menu_entry(_(u"World Scans"), view=views.scanning_management),
                      )),

            menu_entry(_(u"Admin"), views.game_events,
                       (
                         menu_entry(_(u"Game Events"), views.game_events, forced_visibility=(True if user.is_master else False)),
                         menu_entry(_(u"Dashboard"), views.admin_dashboard),
                         menu_entry(_(u"Admin Information"), view=views.admin_information),

                         menu_entry(_(u"Manage Characters"), views.manage_characters),
                         menu_entry(_(u"Manage Webradio Playlist"), views.webradio_management),

                         menu_entry(_(u"Edit Game Items"), views.game_items_management),
                         menu_entry(_(u"Edit Static Pages"), views.static_pages_management),
                         menu_entry(_(u"Edit Email Contacts"), views.global_contacts_management),
                         menu_entry(_(u"Edit Radio Spots"), views.radio_spots_editing),

                         menu_entry(_(u"View Master Manual"), views.gamemaster_manual),

                         menu_entry(_(u"View Database"), views.manage_databases),

                       ),
                      forced_visibility=(True if user.is_master else False)),

            menu_entry(_(u"Profile"), (views.character_profile if user.is_character else views.personal_folder),
                       (
                        menu_entry(view=views.character_profile, forced_visibility=(True if user.is_character else False)), # character only
                        menu_entry(view=views.friendship_management, forced_visibility=(True if user.is_character else False)), # character only
                        menu_entry(view=views.personal_folder),
                        menu_entry(view=views.personal_items_slideshow),
                        menu_entry(_(u"System Events"), views.game_events, forced_visibility=(None if user.is_character else False)),  # might be globally invisible
                        menu_entry(_(u"Log Out"), views.logout, forced_visibility=not user.is_impersonation),
                        ),
                       forced_visibility=(False if not user.is_authenticated else True)),

           menu_entry(_(u"Log In"), views.login, forced_visibility=(False if (user.is_authenticated or user.is_impersonation) else True)),

        ))

    return full_menu_tree



def generate_full_menu(request):

    assert request.datamanager

    def menu_entry_generator(*args, **kwargs):
        """
        Returns a visible *MenuEntry* instance or None,
        depending on the content of the request.
        """
        res = MenuEntry(request, *args, **kwargs)
        return res # no filtering here!

    return _generate_web_menu(request=request, menu_entry_generator=menu_entry_generator)



def filter_menu_tree(menu):
    """
    Recursively removes all invisible items from the tree, including those that TODO FIXME
    """
    recursed_submenus = [filter_menu_tree(submenu) for submenu in menu.submenus]
    menu.submenus = [submenu for submenu in recursed_submenus if submenu] # remove new 'None' entries
    if not menu.is_visible: # NOW only we can query the visibility state of this particular menu entry, since submenus have been updated
        #print(">>>>>>>>>> returning none for", menu.title)
        return None
    return menu


def generate_filtered_menu(request):
    """
    We remove from the base, complete menu, all entries
    that are invisible.
    """
    potential_menu_tree = generate_full_menu(request)
    if potential_menu_tree:
        final_menu_tree = filter_menu_tree(potential_menu_tree)
    else:
        final_menu_tree = None

    if __debug__:
        # we only let VISIBLE entries, both active and inactive !
        if final_menu_tree:
            assert final_menu_tree.is_visible
            final_menu_entries = final_menu_tree.submenus
            for menu in final_menu_entries:
                # print("*", menu.title, menu.is_active, menu.is_visible, menu.user_access)
                assert menu.is_visible
                if menu.submenus:
                    for submenu in menu.submenus:
                        # print(">>>", submenu.title, submenu.is_active, submenu.is_visible, submenu.user_access)
                        assert submenu.is_visible

    return final_menu_tree # might be None, in incredible cases...















'''
    potential_menus = [(_("Main"), information_entries),
                       (_("Communication"), communication_entries),
                       (_("Messaging"), messaging_entries),
                       (_("Administration"), administration_entries)]


    menus = []
    for section_title, potential_menu in potential_menus:
        submenu = []
        for potential_entry in potential_menu:
            if not potential_entry:
                continue

            (name, function) = potential_entry.title, potential_entry.view

            if hasattr(function, "game_master_required"):
                if not user.is_master:
                    continue
            if hasattr(function, "game_permission_required"):
                if not user.is_character:
                    continue
                if function.game_permission_required is not None and not user.has_permission(function.game_permission_required):
                    continue
            if hasattr(function, "game_authenticated_required"):
                if not user.is_authenticated:
                    continue
            submenu.append((name, reverse(function, kwargs=dict(game_instance_id=request.datamanager.game_instance_id))))
        if submenu:
            menus.append((section_title, submenu))

    
    if request.datamanager.player.is_master:
        permission_check = lambda ability: ability.ACCESS in [ACCESSES.master, ACCESSES.guest]
    elif request.datamanager.player.is_authenticated:
        permission_check = (lambda ability: ability.ACCESS == ACCESSES.guest or 
                                            (ability.ACCESS == ACCESSES.player and 
                                             player.has_permission(ability.NAME))
        
    allowed_abilities = [ (ability.TITLE, reverse(abilityview, kwargs=dict(ability_name=ability.NAME) ))  for ability in GameDataManager.ABILITIES_REGISTRY if permission_check(ability)]
    menu_entries += allowed_abilities #HERE TODO - use submenu instead
    '''



"""
# HACK TO ALLOW THE PICKLING OF INSTANCE METHODS #
# WOULD REQUIRE PICKLABILITY OF DATAMANAGER #
import copy_reg
import new
def make_instancemethod(inst, methodname):
    return getattr(inst, methodname)
def pickle_instancemethod(method):
    return make_instancemethod, (method.im_self, method.im_func.__name__)
copy_reg.pickle(new.instancemethod, pickle_instancemethod,
make_instancemethod)



def mark_always_available(func):
    func.requires_global_permission = False
    return func

def _ensure_data_ok(datamanager):
    assert not self.is_shutdown
    
    # TO BE REMOVED !!!!!!!!!!!!!!
    #self._check_database_coherence() # WARNING - quite CPU intensive, to be removed later on ? TODO TODO REMOVE PAKAL !!!
    if not self.is_initialized:
        raise AbnormalUsageError(_("Game databases haven't yet been initialized !"))
            

@decorator
def readonly_method(func, self, *args, **kwargs):
    
    _ensure_data_ok(self)

    original = self.connection._registered_objects[:]
    
    try:
        return func(*args, **kwargs)
    finally:
        final = self.connection._registered_objects[:]
        if original != final:
            s = SequenceMatcher(a=before, b=after)
            
            msg = ""
            for tag, i1, i2, j1, j2 in s.get_opcodes():
              msg += ("%7s a[%d:%d] (%s) b[%d:%d] (%s)\n" % (tag, i1, i2, before[i1:i2], j1, j2, after[j1:j2]))
            
            raise RuntimeError("ZODB was changed by readonly method %s:\n %s" % (func.__name__, msg))

    
    
        
@decorator
def transaction_watcher(func, self, *args, **kwargs): #@NoSelf

    _ensure_data_ok(self)
    

    if not self.get_global_parameter("game_is_started"):
        # some state-changing methods are allowed even before the game starts !
        #if func.__name__ not in ["set_dispatched_message_state_flags", "set_new_message_notification", "force_message_sending",
        #                         "set_online_status"]:
        if getattr(func, "requires_global_permission", True):
            raise UsageError(_("This feature is unavailable at the moment"))

    try:
        savepoint = self.begin()
        res = func(self, *args, **kwargs)
        #self._check_database_coherence() # WARNING - quite CPU intensive, 
        #to be removed later on ? TODO TODO REMOVE PAKAL !!!
        self.commit(savepoint)
        return res
    except Exception:
        self.rollback(savepoint)
        raise

"""



