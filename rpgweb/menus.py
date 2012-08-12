# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from rpgweb import views, abilities
from django.shortcuts import render
from django.template import RequestContext
from difflib import SequenceMatcher
from rpgweb.authentication import AccessResult

    

class MenuEntry:
    
    def __init__(self, request, title, view=None, submenus=None, view_kwargs=None, forced_visibility=None):
        assert isinstance(title, unicode)
        assert view or submenus
        assert view or not view_kwargs
        assert forced_visibility is None or isinstance(forced_visibility, bool)
        
        self.title = title
        
        if view:
            view_kwargs = view_kwargs if view_kwargs else {}
            view_kwargs.update(dict(game_instance_id=request.datamanager.game_instance_id))
            self.url = reverse(view, kwargs=view_kwargs)
        else:
            self.url = None
                                   
        self.submenus = tuple(submenu for submenu in submenus if submenu) if submenus else [] 
        self.user_access = view.get_access_token(request.datamanager)
        self.forced_visibility = forced_visibility
        self.is_active = self.url and (self.user_access == AccessResult.available) # doesn't rely on submenus state
    
    @property
    def is_visible(self):
        if self.forced_visibility is not None:
            return self.forced_visibility
        else:
            return bool(self.submenus or (self.user_access in (AccessResult.available, AccessResult.permission_required)))
        

def generate_full_menu(request):  ## game_menu_generator

    
    assert request.datamanager
      

    datamanager = request.datamanager
    user = datamanager.user
    
        
    def menu_entry(*args, **kwargs):
        """
        Returns a visible *MenuEntry* instance or None,
        depending on the content of the request.
        """
        res = MenuEntry(request, *args, **kwargs)
        return res # no filtering here!


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


    full_menu_tree = menu_entry(_(u"Home"), views.homepage, 
        ( 
            # encoding note : \xa0 <-> &nbsp <-> alt+0160;
                           
            menu_entry(_(u"Home"), views.homepage,
                        (
                           menu_entry(_(u"Home"), views.homepage),
                           menu_entry(_(u"Opening"), views.opening), 
                           menu_entry(_(u"Instructions"), views.instructions), 
                           menu_entry(_(u"Characters"), views.view_characters),
                           menu_entry(_(u"Personal Folder"), views.personal_folder),
                           menu_entry(_(u"Auction"), views.view_sales),
                           menu_entry(_(u"Encyclopedia"), views.view_encyclopedia),
                           menu_entry(_(u"Team Items") if user.is_authenticated else _(u"Auction Items"), views.items_slideshow),
            
                           #menu_entry(_(u"Radio Messages"), views.personal_radio_messages_listing), # TODO INTEGRATE TO INFO PAGES ???
                       )),
            
            menu_entry(_(u"Communication"), views.homepage, # FIXME
                       (
                         menu_entry(_(u"Chatroom") + chatroom_suffix, views.chatroom),
                         menu_entry(_(u"Radio Applet"), views.listen_to_audio_messages, forced_visibility=(False if user.is_character else None))
                      )),
            
            menu_entry(_(u"Messaging"), views.homepage, # FIXME
                      (
                         menu_entry(_(u"Messages") + message_suffix, views.inbox),
                         # ADD ALL OTHER MESSAGING ENTRIES
                      )),
            
            menu_entry(_(u"Admin"), views.homepage, # FIXME
                       (
                         menu_entry(_(u"Dashboard"), abilities.admin_dashboard_view),
                         menu_entry(_(u"Manage Characters"), views.manage_characters),
                        
                         menu_entry(_(u"Game Events"), views.game_events),
                         menu_entry(_(u"Manage Webradio"), views.manage_audio_messages),
                         menu_entry(_(u"Databases"), views.manage_databases),
                      )),
    
    
            menu_entry(_(u"Abilities"), views.homepage, # FIXME
                       (
                      
                        menu_entry(_(u"Wiretaps"), abilities.wiretapping_management_view),
                        menu_entry(_(u"Doors Locking"), abilities.house_locking_view),
                        menu_entry(_(u"Runic Translations"), abilities.runic_translation_view),
    
                        #menu_entry(_(u"Agents Hiring"), views.network_management),
                        #menu_entry(_(u"Oracles"), views.contact_djinns),
                        #menu_entry(_(u"Mercenary Commandos"), views.mercenary_commandos),
                        #menu_entry(_(u"Teleportations"), views.teldorian_teleportations),
                        #menu_entry(_(u"Zealot Attacks"), views.acharith_attacks),
                        #menu_entry(_(u"Telecom Investigations"), views.telecom_investigation),
                        #menu_entry(_(u"World Scans"), views.scanning_management),
                      )),
    
    
    
           menu_entry(_(u"Login"), views.login, forced_visibility=(False if user.is_authenticated else None)),
           menu_entry(_(u"Logout"), views.logout),
        ))

    return full_menu_tree


def filter_menu_tree(menu):
    """
    Recursively removes all invisible items from the tree, including those that TODO FIXME
    """
    recursed_submenus = [filter_menu_tree(submenu) for submenu in menu.submenus]
    menu.submenus = [submenu for submenu in recursed_submenus if submenu] # remove new 'None' entries
    if not menu.is_visible: # NOW only we can query the visibility state of this particular menu entry, since submenus have been updated
        return None
    return menu


def generate_filtered_menu(request):
    potential_menu_tree = generate_full_menu(request)
    final_menu_tree = filter_menu_tree(potential_menu_tree)
    
    if __debug__:
        # we only let VISIBLE entries, both active and inactive !
        assert final_menu_tree.is_visible
        final_menu_entries = final_menu_tree.submenus
        for menu in final_menu_entries:
            #print("*", menu.title, menu.is_active, menu.is_visible, menu.user_access)
            assert menu.is_visible
            if menu.submenus:
                for submenu in menu.submenus:
                    #print(">>>",submenu.title, submenu.is_active, submenu.is_visible, submenu.user_access)
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



