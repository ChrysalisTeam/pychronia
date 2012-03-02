# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from rpgweb import views

from django.shortcuts import render_to_response
from django.template import RequestContext
from difflib import SequenceMatcher
from rpgweb.authentication import AccessResult



    

class MenuEntry:
    
    def __init__(self, request, title, view=None, sub_menus=None, permission_checker=None, view_kwargs=None):
        assert isinstance(title, unicode)
        assert view or sub_menus
        assert view or not view_kwargs
        
        self.title = title
        
        if view:
            view_kwargs = view_kwargs if view_kwargs else {}
            view_kwargs.update(dict(game_instance_id=request.datamanager.game_instance_id))
            self.url = reverse(view, kwargs=view_kwargs)
        else:
            self.url = None
                                   
        self.sub_menus = tuple(sub_menu for sub_menu in sub_menus if sub_menu) if sub_menus else None # we can thus use ternary operator when building the tree

        if permission_checker:
            user_access = permission_checker(request)
        else:
            user_access = view.get_access_token(request)
        
        self.is_visible = self.sub_menus or (user_access in (AccessResult.available, AccessResult.permission_required))
        self.is_active = self.url and (user_access == AccessResult.available)
    


        


def game_menu_generator(request):
    """
    Template context manager which returns template context variables to display customized menus.
    """
    
    if not hasattr(request, "datamanager"):
        return {} # we're not in a valid mystery game instance

    datamanager = request.datamanager
    user = datamanager.user
    
        
    def menu_entry_or_none(*args, **kwargs):
        """
        Returns a visible *MenuEntry* instance or None,
        depending on the content of the request.
        """
        res = MenuEntry(request, *args, **kwargs)
        if res.is_visible:
            return res
        return None


    ## Special additions to menu entries ##
    
    processed_view = request.processed_view # thanks to our middleware
    
    if user.is_authenticated and processed_view != views.inbox: 
        # in inbox, we can set/unset the read state of messages, so the "unread count" must not be considered
        unread_msgs_count = datamanager.get_unread_messages_count(user.username)
        message_suffix = u"(%d)" % unread_msgs_count
    else:
        message_suffix = u""

    if user.is_authenticated and processed_view != views.chatroom:
        # same for chatroom
        num_chatters = len(request.datamanager.get_chatting_users())
        chatroom_suffix = u"(%d)" % num_chatters
    else:
        chatroom_suffix = u""


        
    potential_menus = [    
        # encoding note : \xa0 <-> &nbsp <-> alt+0160;
                       
        menu_entry_or_none(_(u"Home"), views.homepage,
                    (
                       menu_entry_or_none(_(u"Home"), views.homepage),
                       menu_entry_or_none(_(u"Opening"), views.opening), # -> link in homepage, rather 
                       menu_entry_or_none(_(u"Instructions"), views.instructions) if not user.username or user.username.lower() != "loyd.georges" else None, # FIXME warning - hazardous if character changes of name...
                       menu_entry_or_none(_(u"Characters"), views.view_characters),
                       menu_entry_or_none(_(u"Personal Folder"), views.personal_folder),
                       menu_entry_or_none(_(u"Auction"), views.view_sales),
        
                       menu_entry_or_none(_(u"Team Items") if user.is_authenticated else _(u"Auction Items"), views.items_slideshow),
        
                       #menu_entry_or_none(_(u"Radio Messages"), views.personal_radio_messages_listing), # TODO INTEGRATE TO INFO PAGES ???
                   )),
        
        menu_entry_or_none(_(u"Communication"), views.homepage, # FIXME
                   (
                     menu_entry_or_none(_(u"Chatroom") + chatroom_suffix, views.chatroom),
                     menu_entry_or_none(_(u"Radio Applet"), views.listen_to_audio_messages) if not user.is_character else None,
                  )),
        
        menu_entry_or_none(_(u"Messaging"), views.homepage, # FIXME
                  (
                     menu_entry_or_none(_(u"Messages") + message_suffix, views.inbox),
                     # ADD ALL OTHER MESSAGING ENTRIES
                  )),
        
        menu_entry_or_none(_(u"Admin"), views.homepage, # FIXME
                   (
                     menu_entry_or_none(_(u"Game Events"), views.game_events),
                     menu_entry_or_none(_(u"Manage Webradio"), views.manage_audio_messages),
                     menu_entry_or_none(_(u"Databases"), views.manage_databases),
                  )),

                       
        #                         #menu_entry_or_none(_(u"Wiretaps"), views.wiretapping_management),
        #                         #menu_entry_or_none(_(u"Agents Hiring"), views.network_management),
        #                         menu_entry_or_none(_(u"Oracles"), views.contact_djinns),
        #                         menu_entry_or_none(_(u"Mercenary Commandos"), views.mercenary_commandos),
        #                         menu_entry_or_none(_(u"Teleportations"), views.teldorian_teleportations),
        #                         menu_entry_or_none(_(u"Zealot Attacks"), views.acharith_attacks),
        #                         menu_entry_or_none(_(u"Telecom Investigations"), views.telecom_investigation),
        #                         #menu_entry_or_none(_(u"Translations"), views.translations_management),
        #                         menu_entry_or_none(_(u"World Scans"), views.scanning_management),
        #                         menu_entry_or_none(_(u"Doors Locking"), views.domotics_security) if (user.is_master or user.is_anonymous) else None, # TODO FIX THIS


       menu_entry_or_none(_(u"Login"), views.login) if not user.is_authenticated else None,
       
       menu_entry_or_none(_(u"Logout"), views.logout) if user.is_authenticated else None,
    ]

    final_menus = [menu for menu in potential_menus if menu] # top-level filtering
    
    
    if __debug__:
        # we only let VISIBLE entries, both active and inactive !
        for menu in final_menus:
            #print("*", menu.title, menu.is_active)
            assert menu.is_visible
            if menu.sub_menus:
                for sub_menu in menu.sub_menus:
                    #print(">>>",sub_menu.title, sub_menu.is_active)
                    assert sub_menu.is_visible
        
    return final_menus
    '''
    potential_menus = [(_("Main"), information_entries),
                       (_("Communication"), communication_entries),
                       (_("Messaging"), messaging_entries),
                       (_("Administration"), administration_entries)]

        '''
    
    '''
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
    func.always_available = True
    return func

def _ensure_data_ok(datamanager):
    assert not self.is_shutdown
    
    # TO BE REMOVED !!!!!!!!!!!!!!
    #self._check_database_coherency() # WARNING - quite CPU intensive, to be removed later on ? TODO TODO REMOVE PAKAL !!!
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
        #if func.__name__ not in ["set_message_read_state", "set_new_message_notification", "force_message_sending",
        #                         "set_online_status"]:
        if not getattr(func, "always_available", None):
            raise UsageError(_("This feature is unavailable at the moment"))

    try:
        savepoint = self.begin()
        res = func(self, *args, **kwargs)
        #self._check_database_coherency() # WARNING - quite CPU intensive, 
        #to be removed later on ? TODO TODO REMOVE PAKAL !!!
        self.commit(savepoint)
        return res
    except Exception:
        self.rollback(savepoint)
        raise

"""



